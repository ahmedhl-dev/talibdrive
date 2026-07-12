from app import db
from flask_login import UserMixin
from datetime import datetime, timezone

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(200), nullable=False)
    zone_depart = db.Column(db.String(100), nullable=False)
    est_conducteur = db.Column(db.Boolean, default=False)
    vehicule = db.Column(db.String(100), nullable=True)
    telephone = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    email_verifie = db.Column(db.Boolean, default=False)
    code_verification = db.Column(db.String(6), nullable=True)
    code_expiration = db.Column(db.DateTime, nullable=True)
    reset_code = db.Column(db.String(6), nullable=True)
    reset_code_expiration = db.Column(db.DateTime, nullable=True)

    avis_donnes = db.relationship("Avis", foreign_keys="Avis.auteur_id", backref="auteur", lazy=True)
    avis_recus = db.relationship("Avis", foreign_keys="Avis.cible_id", backref="cible", lazy=True)

    trajets = db.relationship("Trajet", backref="conducteur", lazy=True)
    reservations = db.relationship("Reservation", backref="passager", lazy=True)


class Trajet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    depart = db.Column(db.String(150), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    heure = db.Column(db.String(10), nullable=False)
    places_disponibles = db.Column(db.Integer, nullable=False)
    recurrence = db.Column(db.String(20), default="unique")
    conducteur_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    reservations = db.relationship("Reservation", backref="trajet", lazy=True)
    logs = db.relationship("TrajetLog", backref="trajet", lazy=True)


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    statut = db.Column(db.String(20), default="en_attente")
    date_reservation = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    date_specifique = db.Column(db.String(20), nullable=True)
    passager_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trajet_id = db.Column(db.Integer, db.ForeignKey("trajet.id"), nullable=False)


class TrajetLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trajet_id = db.Column(db.Integer, db.ForeignKey("trajet.id"), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default="📋")
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Avis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.id"), nullable=False)
    trajet_id = db.Column(db.Integer, db.ForeignKey("trajet.id"), nullable=False)
    auteur_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    cible_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    note = db.Column(db.Integer, nullable=False)
    commentaire = db.Column(db.String(500), nullable=True)
    tags = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
