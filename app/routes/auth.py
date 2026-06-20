import re
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import User
from app import limiter

auth = Blueprint('auth', __name__)

EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_REGEX = re.compile(r'^[0-9+\-\s]{8,20}$')

@auth.route('/inscription', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def inscription():
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip().lower()
        mot_de_passe = request.form.get('mot_de_passe', '')
        zone_depart = request.form.get('zone_depart', '').strip()
        est_conducteur = True if request.form.get('est_conducteur') else False
        vehicule = request.form.get('vehicule', '').strip()
        telephone = request.form.get('telephone', '').strip()

        errors = []

        if not nom or len(nom) > 100:
            errors.append("Nom invalide.")
        if not prenom or len(prenom) > 100:
            errors.append("Prenom invalide.")
        if not EMAIL_REGEX.match(email) or len(email) > 150:
            errors.append("Email invalide.")
        if len(mot_de_passe) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caracteres.")
        if not zone_depart or len(zone_depart) > 100:
            errors.append("Zone de depart invalide.")
        if est_conducteur and not telephone:
            errors.append("Le numero de telephone est obligatoire pour les conducteurs.")
        if telephone and not PHONE_REGEX.match(telephone):
            errors.append("Numero de telephone invalide.")
        if vehicule and len(vehicule) > 100:
            errors.append("Nom du vehicule trop long.")

        if errors:
            for e in errors:
                flash(e, 'error')
            return redirect(url_for('auth.inscription'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Cet email est deja utilise.', 'error')
            return redirect(url_for('auth.inscription'))

        hashed_password = generate_password_hash(mot_de_passe)
        new_user = User(
            nom=nom, prenom=prenom, email=email,
            mot_de_passe=hashed_password, zone_depart=zone_depart,
            est_conducteur=est_conducteur, vehicule=vehicule or None,
            telephone=telephone or None
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Compte cree avec succes!', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/inscription.html')


@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("15 per hour")
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        mot_de_passe = request.form.get('mot_de_passe', '')
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.mot_de_passe, mot_de_passe):
            flash('Email ou mot de passe incorrect.', 'error')
            return redirect(url_for('auth.login'))

        login_user(user)
        return redirect(url_for('trajets.index'))

    return render_template('auth/login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
