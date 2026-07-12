from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Trajet, Reservation, TrajetLog, Avis
from werkzeug.security import generate_password_hash
from functools import wraps

admin = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Accès refusé.", "error")
            return redirect(url_for("trajets.index"))
        return f(*args, **kwargs)
    return decorated

@admin.route("/")
@login_required
@admin_required
def index():
    users = User.query.all()
    trajets = Trajet.query.all()
    reservations = Reservation.query.all()
    avis_signales = Avis.query.filter(Avis.note <= 2).order_by(Avis.created_at.desc()).all()
    return render_template("admin/index.html", users=users, trajets=trajets, reservations=reservations, avis_signales=avis_signales)

@admin.route("/supprimer/user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def supprimer_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash("Impossible de supprimer un administrateur.", "error")
        return redirect(url_for("admin.index"))

    Reservation.query.filter_by(passager_id=user.id).delete()
    for trajet in Trajet.query.filter_by(conducteur_id=user.id).all():
        Reservation.query.filter_by(trajet_id=trajet.id).delete()
        TrajetLog.query.filter_by(trajet_id=trajet.id).delete()
        db.session.delete(trajet)

    db.session.delete(user)
    db.session.commit()
    flash("Utilisateur supprimé.", "success")
    return redirect(url_for("admin.index"))

@admin.route("/supprimer/trajet/<int:trajet_id>", methods=["POST"])
@login_required
@admin_required
def supprimer_trajet(trajet_id):
    trajet = Trajet.query.get_or_404(trajet_id)
    Reservation.query.filter_by(trajet_id=trajet.id).delete()
    TrajetLog.query.filter_by(trajet_id=trajet.id).delete()
    db.session.delete(trajet)
    db.session.commit()
    flash("Trajet supprimé.", "success")
    return redirect(url_for("admin.index"))

@admin.route("/supprimer/reservation/<int:res_id>", methods=["POST"])
@login_required
@admin_required
def supprimer_reservation(res_id):
    res = Reservation.query.get_or_404(res_id)
    db.session.delete(res)
    db.session.commit()
    flash("Réservation supprimée.", "success")
    return redirect(url_for("admin.index"))

@admin.route("/modifier/user/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def modifier_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        email = request.form.get("email", "").strip().lower()
        nouveau_mdp = request.form.get("nouveau_mdp", "").strip()

        errors = []
        if not nom or len(nom) > 100:
            errors.append("Nom invalide.")
        if not prenom or len(prenom) > 100:
            errors.append("Prénom invalide.")
        if not email or "@" not in email or len(email) > 150:
            errors.append("Email invalide.")

        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            errors.append("Cet email est déjà utilisé par un autre compte.")

        if nouveau_mdp and len(nouveau_mdp) < 8:
            errors.append("Le nouveau mot de passe doit contenir au moins 8 caractères.")

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("admin.modifier_user", user_id=user.id))

        user.nom = nom
        user.prenom = prenom
        user.email = email
        if nouveau_mdp:
            user.mot_de_passe = generate_password_hash(nouveau_mdp)

        db.session.commit()
        flash("Utilisateur modifié avec succès.", "success")
        return redirect(url_for("admin.index"))

    return render_template("admin/modifier_user.html", user=user)
