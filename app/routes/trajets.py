from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import Trajet, Avis
from datetime import date, datetime, timedelta, timezone

trajets = Blueprint("trajets", __name__)

@trajets.route("/")
@login_required
def index():
    now = datetime.now(timezone.utc)
    today = date.today().isoformat()
    now_time = now.strftime("%H:%M")

    tous_trajets = Trajet.query.filter(
        Trajet.places_disponibles > 0
    ).filter(
        db.or_(
            Trajet.recurrence == "quotidien",
            Trajet.date > today,
            db.and_(
                Trajet.date == today,
                Trajet.heure > now_time
            )
        )
    ).order_by(Trajet.date, Trajet.heure).all()

    ratings = {}
    for trajet in tous_trajets:
        avis_list = Avis.query.filter_by(cible_id=trajet.conducteur_id).all()
        if avis_list:
            avg = sum(a.note for a in avis_list) / len(avis_list)
            ratings[trajet.conducteur_id] = {"avg": round(avg, 1), "count": len(avis_list)}

    return render_template("trajets/index.html", trajets=tous_trajets, ratings=ratings)


@trajets.route("/proposer", methods=["GET", "POST"])
@login_required
def proposer():
    if not current_user.est_conducteur:
        flash("Seuls les conducteurs peuvent proposer un trajet.", "error")
        return redirect(url_for("trajets.index"))

    if request.method == "POST":
        depart = request.form.get("depart", "").strip()
        date_str = request.form.get("date", "").strip()
        heure = request.form.get("heure", "").strip()
        places_raw = request.form.get("places_disponibles", "").strip()
        recurrence = request.form.get("recurrence", "unique").strip()

        errors = []

        if not depart or len(depart) > 150:
            errors.append("Le point de départ est invalide.")

        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if parsed_date < date.today():
                errors.append("La date ne peut pas être dans le passé.")
            if parsed_date > date.today() + timedelta(days=365):
                errors.append("La date est trop loin dans le futur.")
        except (ValueError, TypeError):
            errors.append("Date invalide.")

        try:
            datetime.strptime(heure, "%H:%M")
        except (ValueError, TypeError):
            errors.append("Heure invalide.")

        try:
            places = int(places_raw)
            if places < 1 or places > 8:
                errors.append("Le nombre de places doit être entre 1 et 8.")
        except (ValueError, TypeError):
            errors.append("Nombre de places invalide.")
            places = None

        if recurrence not in ("unique", "quotidien"):
            errors.append("Récurrence invalide.")

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("trajets.proposer"))

        trajet = Trajet(
            depart=depart,
            destination="FSJES Mohammedia",
            date=date_str,
            heure=heure,
            places_disponibles=places,
            recurrence=recurrence,
            conducteur_id=current_user.id
        )
        db.session.add(trajet)
        db.session.commit()
        flash("Trajet proposé avec succès !", "success")
        return redirect(url_for("trajets.index"))

    return render_template("trajets/proposer.html")


@trajets.route("/trajet/<int:trajet_id>")
@login_required
def detail(trajet_id):
    trajet = Trajet.query.get_or_404(trajet_id)
    if trajet.conducteur_id != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for("trajets.index"))

    en_attente = [r for r in trajet.reservations if r.statut == "en_attente"]
    confirmes = [r for r in trajet.reservations if r.statut == "confirmee"]

    today = date.today()
    try:
        start = max(datetime.strptime(trajet.date, "%Y-%m-%d").date(), today)
    except (ValueError, TypeError):
        start = today

    day_names = ["Lun", "Mar", "Mer", "Jeu", "Ven"]
    week_days = []
    d = start
    while len(week_days) < 5:
        if d.weekday() < 5:
            week_days.append({
                "iso": d.isoformat(),
                "label": day_names[d.weekday()],
                "date": d.strftime("%d/%m")
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

    return render_template("trajets/detail.html",
        trajet=trajet,
        en_attente=en_attente,
        confirmes=confirmes,
        week_days=week_days,
        confirmed_per_day=confirmed_per_day,
        pending_per_day=pending_per_day
    )
