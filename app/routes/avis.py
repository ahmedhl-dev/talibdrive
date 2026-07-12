from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import Reservation, Avis
from datetime import datetime, timezone

avis = Blueprint("avis", __name__)

TAGS_CONDUCTEUR = ["Ponctuel", "Véhicule propre", "Bonne conduite", "Sympathique"]
TAGS_PASSAGER = ["Ponctuel", "Poli", "Respectueux", "Bonne communication"]


def get_trip_datetime(trajet, date_specifique=None):
    date_str = date_specifique if date_specifique else trajet.date
    try:
        return datetime.strptime(f"{date_str} {trajet.heure}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


@avis.route("/noter/<int:res_id>/<int:cible_id>", methods=["GET", "POST"])
@login_required
def noter(res_id, cible_id):
    res = Reservation.query.get_or_404(res_id)
    trajet = res.trajet

    is_passager = res.passager_id == current_user.id
    is_conducteur = trajet.conducteur_id == current_user.id

    if not is_passager and not is_conducteur:
        abort(403)

    if is_passager and cible_id != trajet.conducteur_id:
        abort(403)
    if is_conducteur and cible_id != res.passager_id:
        abort(403)

    if res.statut != "confirmee":
        flash("Cette réservation n'est pas confirmée.", "error")
        return redirect(url_for("reservations.mes_reservations"))

    trip_dt = get_trip_datetime(trajet, res.date_specifique)
    if not trip_dt or trip_dt > datetime.now(timezone.utc):
        flash("Ce trajet n'a pas encore eu lieu.", "error")
        return redirect(url_for("reservations.mes_reservations"))

    existing = Avis.query.filter_by(reservation_id=res_id, auteur_id=current_user.id, cible_id=cible_id).first()
    if existing:
        flash("Vous avez déjà noté ce trajet.", "error")
        return redirect(url_for("reservations.mes_reservations"))

    tags_options = TAGS_CONDUCTEUR if is_passager else TAGS_PASSAGER

    if request.method == "POST":
        note = request.form.get("note", "")
        commentaire = request.form.get("commentaire", "").strip()
        selected_tags = request.form.getlist("tags")

        try:
            note = int(note)
            if note < 1 or note > 5:
                raise ValueError
        except ValueError:
            flash("Note invalide.", "error")
            return redirect(url_for("avis.noter", res_id=res_id, cible_id=cible_id))

        valid_tags = [t for t in selected_tags if t in tags_options]
        if len(commentaire) > 500:
            commentaire = commentaire[:500]

        new_avis = Avis(
            reservation_id=res_id,
            trajet_id=trajet.id,
            auteur_id=current_user.id,
            cible_id=cible_id,
            note=note,
            commentaire=commentaire or None,
            tags=",".join(valid_tags) if valid_tags else None
        )
        db.session.add(new_avis)
        db.session.commit()
        flash("Merci pour votre avis !", "success")
        return redirect(url_for("reservations.mes_reservations"))

    cible = res.passager if is_conducteur else trajet.conducteur
    return render_template("avis/noter.html", res=res, trajet=trajet, cible=cible, tags_options=tags_options, is_passager=is_passager)
