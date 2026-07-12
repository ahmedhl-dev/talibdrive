import re
import random
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, limiter
from app.models import User
from app.email_utils import send_verification_email, send_reset_email

auth = Blueprint('auth', __name__)

EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_REGEX = re.compile(r'^[0-9+\-\s]{8,20}$')

def generate_code():
    return str(random.randint(100000, 999999))

@auth.route('/inscription', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def inscription():
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip().lower()
        mot_de_passe = request.form.get('mot_de_passe', '')
        confirmer_mot_de_passe = request.form.get('confirmer_mot_de_passe', '')
        zone_depart = request.form.get('zone_depart', '').strip()
        est_conducteur = True if request.form.get('est_conducteur') else False
        vehicule = request.form.get('vehicule', '').strip()
        telephone = request.form.get('telephone', '').strip()

        errors = []

        if not nom or len(nom) > 100:
            errors.append("Nom invalide.")
        if not prenom or len(prenom) > 100:
            errors.append("Prénom invalide.")
        if not EMAIL_REGEX.match(email) or len(email) > 150:
            errors.append("Email invalide.")
        if len(mot_de_passe) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caractères.")
        if mot_de_passe != confirmer_mot_de_passe:
            errors.append("Les mots de passe ne correspondent pas.")
        if not zone_depart or len(zone_depart) > 100:
            errors.append("Zone de départ invalide.")
        if est_conducteur and not telephone:
            errors.append("Le numéro de téléphone est obligatoire pour les conducteurs.")
        if telephone and not PHONE_REGEX.match(telephone):
            errors.append("Numéro de téléphone invalide.")
        if vehicule and len(vehicule) > 100:
            errors.append("Nom du véhicule trop long.")

        if errors:
            for e in errors:
                flash(e, 'error')
            return redirect(url_for('auth.inscription'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Cet email est déjà utilisé.', 'error')
            return redirect(url_for('auth.inscription'))

        code = generate_code()
        hashed_password = generate_password_hash(mot_de_passe)
        new_user = User(
            nom=nom, prenom=prenom, email=email,
            mot_de_passe=hashed_password, zone_depart=zone_depart,
            est_conducteur=est_conducteur, vehicule=vehicule or None,
            telephone=telephone or None,
            email_verifie=False,
            code_verification=code,
            code_expiration=datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        db.session.add(new_user)
        db.session.commit()

        sent = send_verification_email(email, prenom, code)
        if not sent:
            flash("Compte créé, mais l'envoi de l'email a échoué. Contactez l'administrateur.", "error")

        session['pending_verification_email'] = email
        flash('Compte créé ! Vérifiez votre email pour activer votre compte.', 'success')
        return redirect(url_for('auth.verifier_email'))

    return render_template('auth/inscription.html')


@auth.route('/verifier-email', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
def verifier_email():
    email = session.get('pending_verification_email')
    if not email:
        flash('Session expirée. Veuillez vous inscrire à nouveau.', 'error')
        return redirect(url_for('auth.inscription'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Utilisateur introuvable.', 'error')
        return redirect(url_for('auth.inscription'))

    if user.email_verifie:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code_entre = request.form.get('code', '').strip()

        if not user.code_expiration or datetime.now(timezone.utc) > user.code_expiration.replace(tzinfo=timezone.utc):
            flash('Le code a expiré. Demandez un nouveau code.', 'error')
            return redirect(url_for('auth.verifier_email'))

        if code_entre != user.code_verification:
            flash('Code incorrect.', 'error')
            return redirect(url_for('auth.verifier_email'))

        user.email_verifie = True
        user.code_verification = None
        user.code_expiration = None
        db.session.commit()
        session.pop('pending_verification_email', None)

        login_user(user)
        flash('Email vérifié avec succès ! Bienvenue sur TalibDrive.', 'success')
        return redirect(url_for('trajets.index'))

    return render_template('auth/verifier_email.html', email=email)


@auth.route('/renvoyer-code')
@limiter.limit("5 per hour")
def renvoyer_code():
    email = session.get('pending_verification_email')
    if not email:
        flash('Session expirée.', 'error')
        return redirect(url_for('auth.inscription'))

    user = User.query.filter_by(email=email).first()
    if not user or user.email_verifie:
        return redirect(url_for('auth.login'))

    code = generate_code()
    user.code_verification = code
    user.code_expiration = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.session.commit()

    sent = send_verification_email(email, user.prenom, code)
    if sent:
        flash('Un nouveau code a été envoyé.', 'success')
    else:
        flash("Erreur lors de l'envoi du code.", 'error')

    return redirect(url_for('auth.verifier_email'))


@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per hour")
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        mot_de_passe = request.form.get('mot_de_passe', '')
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.mot_de_passe, mot_de_passe):
            flash('Email ou mot de passe incorrect.', 'error')
            return redirect(url_for('auth.login'))

        if not user.email_verifie:
            session['pending_verification_email'] = user.email
            flash('Veuillez vérifier votre email avant de vous connecter.', 'error')
            return redirect(url_for('auth.verifier_email'))

        login_user(user)
        return redirect(url_for('trajets.index'))

    return render_template('auth/login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/mot-de-passe-oublie', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def mot_de_passe_oublie():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            code = generate_code()
            user.reset_code = code
            user.reset_code_expiration = datetime.now(timezone.utc) + timedelta(minutes=15)
            db.session.commit()
            send_reset_email(user.email, user.prenom, code)

        session['pending_reset_email'] = email
        flash("Si ce compte existe, un code de réinitialisation a été envoyé.", "success")
        return redirect(url_for('auth.reinitialiser_mot_de_passe'))

    return render_template('auth/mot_de_passe_oublie.html')


@auth.route('/reinitialiser-mot-de-passe', methods=['GET', 'POST'])
@limiter.limit("15 per hour")
def reinitialiser_mot_de_passe():
    email = session.get('pending_reset_email')
    if not email:
        flash('Session expirée. Recommencez.', 'error')
        return redirect(url_for('auth.mot_de_passe_oublie'))

    if request.method == 'POST':
        code_entre = request.form.get('code', '').strip()
        nouveau_mdp = request.form.get('nouveau_mdp', '')
        confirmer_mdp = request.form.get('confirmer_mdp', '')

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Utilisateur introuvable.', 'error')
            return redirect(url_for('auth.mot_de_passe_oublie'))

        if not user.reset_code_expiration or datetime.now(timezone.utc) > user.reset_code_expiration.replace(tzinfo=timezone.utc):
            flash('Le code a expiré. Demandez un nouveau code.', 'error')
            return redirect(url_for('auth.mot_de_passe_oublie'))

        if code_entre != user.reset_code:
            flash('Code incorrect.', 'error')
            return redirect(url_for('auth.reinitialiser_mot_de_passe'))

        if len(nouveau_mdp) < 8:
            flash('Le mot de passe doit contenir au moins 8 caractères.', 'error')
            return redirect(url_for('auth.reinitialiser_mot_de_passe'))

        if nouveau_mdp != confirmer_mdp:
            flash('Les mots de passe ne correspondent pas.', 'error')
            return redirect(url_for('auth.reinitialiser_mot_de_passe'))

        user.mot_de_passe = generate_password_hash(nouveau_mdp)
        user.reset_code = None
        user.reset_code_expiration = None
        db.session.commit()
        session.pop('pending_reset_email', None)

        flash('Mot de passe réinitialisé avec succès. Connectez-vous.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reinitialiser_mot_de_passe.html', email=email)


@auth.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    if request.method == 'POST':
        mdp_actuel = request.form.get('mdp_actuel', '')
        nouveau_mdp = request.form.get('nouveau_mdp', '')
        confirmer_mdp = request.form.get('confirmer_mdp', '')

        if not check_password_hash(current_user.mot_de_passe, mdp_actuel):
            flash('Mot de passe actuel incorrect.', 'error')
            return redirect(url_for('auth.profil'))

        if len(nouveau_mdp) < 8:
            flash('Le nouveau mot de passe doit contenir au moins 8 caractères.', 'error')
            return redirect(url_for('auth.profil'))

        if nouveau_mdp != confirmer_mdp:
            flash('Les mots de passe ne correspondent pas.', 'error')
            return redirect(url_for('auth.profil'))

        current_user.mot_de_passe = generate_password_hash(nouveau_mdp)
        db.session.commit()
        flash('Mot de passe modifié avec succès.', 'success')
        return redirect(url_for('auth.profil'))

    return render_template('auth/profil.html')
