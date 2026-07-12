from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Reservation, Trajet, TrajetLog, Avis
from datetime import datetime, timezone, timedelta, date as date_type

reservations = Blueprint("reservations", __name__)

def log(trajet_id, emoji, message):
    entry = TrajetLog(trajet_id=trajet_id, emoji=emoji, message=message)
    db.session.add(entry)

def get_trip_datetime(trajet, date_specifique=None):
    date_str = date_specifique if date_specifique else trajet.date
    try:
        return datetime.strptime(f"{date_str} {trajet.heure}", "%Y-%m-%d %H:%M")
    except:
        return None

def places_restantes_pour_date(trajet, date_str):
    confirmed_count = Reservation.query.filter_by(
        trajet_id=trajet.id, date_specifique=date_str, statut="confirmee"
    ).count()
    pending_count = Reservation.query.filter_by(
        trajet_id=trajet.id, date_specifique=date_str, statut="en_attente"
    ).count()
    return trajet.places_disponibles - confirmed_count - pending_count

def get_weekdays_in_range(start_str, end_str):
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    except:
        return []
    if start > end:
        return []
    if (end - start).days > 31:
        return []
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


@reservations.route("/reserver/<int:trajet_id>", methods=["GET", "POST"])
@login_required
def reserver(trajet_id):
    trajet = Trajet.query.get_or_404(trajet_id)

    if trajet.conducteur_id == current_user.id:
        flash("Vous ne pouvez pas reserver votre propre trajet.", "error")
        return redirect(url_for("trajets.index"))

    if trajet.recurrence == "unique" and trajet.places_disponibles <= 0:
        flash("Plus de places disponibles.", "error")
        return redirect(url_for("trajets.index"))

    if trajet.recurrence == "quotidien" and request.method == "GET":
        today = date_type.today()
        try:
            start = max(datetime.strptime(trajet.date, "%Y-%m-%d").date(), today)
        except:
            start = today
        day_names = ["Lun", "Mar", "Mer", "Jeu", "Ven"]
        week_days = []
        d = start
        while len(week_days) < 5:
            if d.weekday() < 5:
                week_days.append({
                    "iso": d.isoformat(),
                    "label": day_names[d.weekday()],
                    "date": d.strftime("%d/%m"),
                    "is_past": False
                })
            d += timedelta(days=1)

        confirmed_per_day = {}
        pending_per_day = {}
        for res in trajet.reservations:
            if res.date_specifique:
                if res.statut == "confirmee":
                    confirmed_per_day[res.date_specifique] = confirmed_per_day.get(res.date_specifique, 0) + 1
                elif res.statut == "en_attente":
                    pending_per_day[res.date_specifique] = pending_per_day.get(res.date_specifique, 0) + 1

        return render_template("reservations/choisir_date.html",
            trajet=trajet, today=today.isoformat(),
            week_days=week_days,
            confirmed_per_day=confirmed_per_day,
            pending_per_day=pending_per_day
        )

    if trajet.recurrence == "unique":
        existing = Reservation.query.filter_by(
            passager_id=current_user.id, trajet_id=trajet_id
        ).first()
        if existing:
            flash("Vous avez deja une reservation pour ce trajet.", "error")
            return redirect(url_for("trajets.index"))

        reservation = Reservation(
            passager_id=current_user.id, trajet_id=trajet_id,
            statut="en_attente", date_specifique=None
        )
        db.session.add(reservation)
        log(trajet_id, "🟡",
            f"{current_user.prenom} {current_user.nom} a demande une place — {trajet.depart} → FSJES Mohammedia, {trajet.date} a {trajet.heure}"
        )
        db.session.commit()
        flash("Demande de reservation envoyee avec succes!", "success")
        return redirect(url_for("trajets.index"))

    # quotidien logic
    date_debut = request.form.get("date_debut", "").strip()
    date_fin = request.form.get("date_fin", "").strip()

    if not date_debut or not date_fin:
        flash("Veuillez choisir une periode.", "error")
        return redirect(url_for("reservations.reserver", trajet_id=trajet_id))

    today_str = date_type.today().isoformat()

    if date_debut < today_str:
        flash("La date de debut ne peut pas etre dans le passe.", "error")
        return redirect(url_for("reservations.reserver", trajet_id=trajet_id))

    if date_fin < date_debut:
        flash("La date de fin doit etre apres la date de debut.", "error")
        return redirect(url_for("reservations.reserver", trajet_id=trajet_id))

    weekdays = get_weekdays_in_range(date_debut, date_fin)

    if not weekdays:
        flash("Periode invalide (max 31 jours, jours ouvrables uniquement).", "error")
        return redirect(url_for("reservations.reserver", trajet_id=trajet_id))

    booked, skipped_full, skipped_duplicate = [], [], []

    for day in weekdays:
        existing = Reservation.query.filter_by(
            passager_id=current_user.id, trajet_id=trajet_id, date_specifique=day
        ).first()
        if existing:
            skipped_duplicate.append(day)
            continue

        restantes = places_restantes_pour_date(trajet, day)
        if restantes <= 0:
            skipped_full.append(day)
            continue

        reservation = Reservation(
            passager_id=current_user.id, trajet_id=trajet_id,
            statut="en_attente", date_specifique=day
        )
        db.session.add(reservation)
        booked.append(day)

    if booked:
        log(trajet_id, "🟡",
            f"{current_user.prenom} {current_user.nom} a demande {len(booked)} place(s) — {trajet.depart} → FSJES Mohammedia, du {booked[0]} au {booked[-1]} a {trajet.heure}"
        )

    db.session.commit()

    if booked:
        flash(f"{len(booked)} reservation(s) envoyee(s) avec succes!", "success")
    if skipped_full:
        flash(f"{len(skipped_full)} jour(s) saute(s) car complet: {', '.join(skipped_full)}", "error")
    if skipped_duplicate:
        flash(f"{len(skipped_duplicate)} jour(s) deja reserve(s): {', '.join(skipped_duplicate)}", "error")
    if not booked:
        flash("Aucune reservation effectuee.", "error")

    return redirect(url_for("trajets.index"))


@reservations.route("/mes-reservations")
@login_required
def mes_reservations():
    today_str = date_type.today().isoformat()

    mes_res_raw = Reservation.query.filter_by(passager_id=current_user.id).all()

    mes_res = []
    for r in mes_res_raw:
        if r.date_specifique:
            if r.date_specifique >= today_str:
                mes_res.append(r)
        else:
            if r.trajet.date >= today_str:
                mes_res.append(r)

    demandes = []
    logs = []

    if current_user.est_conducteur:
        for trajet in current_user.trajets:
            for res in trajet.reservations:
                if res.date_specifique:
                    if res.date_specifique >= today_str:
                        demandes.append(res)
                else:
                    if res.trajet.date >= today_str:
                        demandes.append(res)
            for entry in sorted(trajet.logs, key=lambda x: x.timestamp, reverse=True):
                logs.append(entry)

    confirmed = [r for r in mes_res_raw if r.statut == "confirmee"]
    co2_economise = round(len(confirmed) * 20 * 0.21, 2)

    return render_template("reservations/mes_reservations.html",
        mes_res=mes_res, demandes=demandes, logs=logs, co2_economise=co2_economise
    )


@reservations.route("/reservation/<int:res_id>/<action>", methods=["POST"])
@login_required
def action_reservation(res_id, action):
    if action not in ("annuler", "confirmer", "refuser"):
        abort(400)

    res = Reservation.query.get_or_404(res_id)
    trajet = res.trajet
    passager = res.passager
    date_label = f"le {res.date_specifique}" if res.date_specifique else trajet.date

    is_owner_passager = res.passager_id == current_user.id
    is_owner_conducteur = trajet.conducteur_id == current_user.id

    # explicit authorization check — reject anything that doesn't match
    if action == "annuler" and not is_owner_passager:
        abort(403)
    if action in ("confirmer", "refuser") and not is_owner_conducteur:
        abort(403)

    if action == "annuler":
        trip_dt = get_trip_datetime(trajet, res.date_specifique)
        now = datetime.now()

        if trip_dt and (trip_dt - now) < timedelta(hours=2):
            log(trajet.id, "🔒",
                f"{current_user.prenom} {current_user.nom} a tente d'annuler trop tard — moins de 2h avant le depart ({date_label} a {trajet.heure})"
            )
            db.session.commit()
            flash("Annulation impossible — moins de 2h avant le depart.", "error")
            return redirect(url_for("reservations.mes_reservations"))

        was_confirmed = res.statut == "confirmee"
        log(trajet.id, "🔴",
            f"{current_user.prenom} {current_user.nom} a annule sa reservation — {trajet.depart} → FSJES Mohammedia, {date_label} a {trajet.heure}"
        )
        if was_confirmed and not res.date_specifique:
            trajet.places_disponibles += 1
        db.session.delete(res)
        db.session.commit()
        flash("Reservation annulee.", "success")
        return redirect(url_for("reservations.mes_reservations"))

    elif action == "confirmer":
        if res.date_specifique:
            restantes = places_restantes_pour_date(trajet, res.date_specifique)
            if restantes <= 0:
                flash("Plus de places disponibles pour cette date.", "error")
                return redirect(url_for("trajets.detail", trajet_id=trajet.id))

        res.statut = "confirmee"
        if not res.date_specifique:
            trajet.places_disponibles -= 1
        log(trajet.id, "✅",
            f"Vous avez confirme la reservation de {passager.prenom} {passager.nom} — {date_label} a {trajet.heure}"
        )
        db.session.commit()
        flash("Reservation confirmee!", "success")
        return redirect(url_for("trajets.detail", trajet_id=trajet.id))

    elif action == "refuser":
        res.statut = "refusee"
        log(trajet.id, "❌",
            f"Vous avez refuse la reservation de {passager.prenom} {passager.nom} — {date_label} a {trajet.heure}"
        )
        db.session.commit()
        flash("Reservation refusee.", "success")
        return redirect(url_for("trajets.detail", trajet_id=trajet.id))
