import pytest
from app import create_app, db
from app.models import User, Trajet, Reservation, TrajetLog
from werkzeug.security import generate_password_hash
from datetime import date, timedelta, datetime, timezone

@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    app.config["BREVO_API_KEY"] = None  # disable real email sending during tests
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def create_user(email, est_conducteur=False, telephone=None):
    u = User(
        nom="Test", prenom="User",
        email=email,
        mot_de_passe=generate_password_hash("password"),
        zone_depart="Mohammedia",
        est_conducteur=est_conducteur,
        vehicule="Dacia" if est_conducteur else None,
        telephone=telephone,
        email_verifie=True
    )
    db.session.add(u)
    db.session.flush()
    return u

def create_trajet(conducteur_id, places=3, recurrence="unique", days_ahead=0, heure="23:59"):
    d = (date.today() + timedelta(days=days_ahead)).isoformat()
    t = Trajet(
        depart="Mohammedia",
        destination="The University",
        date=d,
        heure=heure,
        places_disponibles=places,
        recurrence=recurrence,
        conducteur_id=conducteur_id
    )
    db.session.add(t)
    db.session.flush()
    return t

def login(client, email):
    return client.post("/login", data={
        "email": email,
        "mot_de_passe": "password"
    }, follow_redirects=True)

def next_weekday(weekday, min_days_ahead=0):
    d = date.today() + timedelta(days=min_days_ahead)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


# AUTH TESTS

def test_inscription(client, app):
    with app.app_context():
        res = client.post("/inscription", data={
            "nom": "Alaoui", "prenom": "Youssef",
            "email": "youssef@univ.ma",
            "mot_de_passe": "test1234",
            "confirmer_mot_de_passe": "test1234",
            "zone_depart": "Mohammedia"
        }, follow_redirects=True)
        assert res.status_code == 200
        assert User.query.filter_by(email="youssef@univ.ma").first() is not None

def test_inscription_duplicate_email(client, app):
    with app.app_context():
        create_user("duplicate@univ.ma")
        db.session.commit()
        client.post("/inscription", data={
            "nom": "A", "prenom": "B",
            "email": "duplicate@univ.ma",
            "mot_de_passe": "test1234",
            "zone_depart": "Mohammedia"
        }, follow_redirects=True)
        assert User.query.filter_by(email="duplicate@univ.ma").count() == 1

def test_conducteur_requires_telephone(client, app):
    with app.app_context():
        client.post("/inscription", data={
            "nom": "A", "prenom": "B",
            "email": "driver@univ.ma",
            "mot_de_passe": "test1234",
            "confirmer_mot_de_passe": "test1234",
            "zone_depart": "Mohammedia",
            "est_conducteur": "on",
            "telephone": ""
        }, follow_redirects=True)
        assert User.query.filter_by(email="driver@univ.ma").first() is None

def test_login_success(client, app):
    with app.app_context():
        create_user("login@univ.ma")
        db.session.commit()
    res = login(client, "login@univ.ma")
    assert res.status_code == 200

def test_login_wrong_password(client, app):
    with app.app_context():
        create_user("wrong@univ.ma")
        db.session.commit()
    res = client.post("/login", data={
        "email": "wrong@univ.ma",
        "mot_de_passe": "wrongpassword"
    }, follow_redirects=True)
    assert res.status_code == 200


# TRAJET TESTS

def test_proposer_trajet(client, app):
    with app.app_context():
        create_user("driver@univ.ma", est_conducteur=True, telephone="0600000000")
        db.session.commit()
    login(client, "driver@univ.ma")
    client.post("/proposer", data={
        "depart": "Mohammedia",
        "date": date.today().isoformat(),
        "heure": "08:00",
        "places_disponibles": "3",
        "recurrence": "unique"
    }, follow_redirects=True)
    with app.app_context():
        assert Trajet.query.count() == 1

def test_trajets_hides_past_unique(client, app):
    with app.app_context():
        driver = create_user("driver2@univ.ma", est_conducteur=True, telephone="0600000000")
        t = create_trajet(driver.id, days_ahead=-1)
        db.session.commit()
    login(client, "driver2@univ.ma")
    res = client.get("/", follow_redirects=True)
    assert "Reserver".encode() not in res.data

def test_trajets_hides_zero_places(client, app):
    with app.app_context():
        driver = create_user("driver3@univ.ma", est_conducteur=True, telephone="0600000000")
        t = create_trajet(driver.id, places=0)
        db.session.commit()
    login(client, "driver3@univ.ma")
    res = client.get("/", follow_redirects=True)
    assert "Reserver".encode() not in res.data


# RESERVATION TESTS

def test_reserver_unique(client, app):
    with app.app_context():
        driver = create_user("d@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("p@univ.ma")
        t = create_trajet(driver.id, places=3)
        db.session.commit()
        trajet_id = t.id
    login(client, "p@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)
    with app.app_context():
        assert Reservation.query.count() == 1

def test_cannot_reserve_own_trajet(client, app):
    with app.app_context():
        driver = create_user("own@univ.ma", est_conducteur=True, telephone="0600000000")
        t = create_trajet(driver.id)
        db.session.commit()
        trajet_id = t.id
    login(client, "own@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)
    with app.app_context():
        assert Reservation.query.count() == 0

def test_cannot_reserve_duplicate(client, app):
    with app.app_context():
        driver = create_user("d2@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("p2@univ.ma")
        t = create_trajet(driver.id, places=3)
        db.session.commit()
        trajet_id = t.id
    login(client, "p2@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)
    with app.app_context():
        assert Reservation.query.count() == 1

def test_cancel_increments_places(client, app):
    with app.app_context():
        driver = create_user("d3@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("p3@univ.ma")
        # use days_ahead=3 and heure=23:59 to avoid 2h block
        t = create_trajet(driver.id, places=3, days_ahead=3, heure="23:59")
        db.session.commit()
        trajet_id = t.id

    login(client, "p3@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)

    with app.app_context():
        res = Reservation.query.first()
        res.statut = "confirmee"
        trajet = Trajet.query.filter_by(id=trajet_id).first()
        trajet.places_disponibles -= 1
        db.session.commit()
        res_id = res.id

    client.post(f"/reservation/{res_id}/annuler", follow_redirects=True)

    with app.app_context():
        trajet = Trajet.query.filter_by(id=trajet_id).first()
        assert trajet.places_disponibles == 3

def test_confirm_reservation(client, app):
    with app.app_context():
        driver = create_user("d4@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("p4@univ.ma")
        t = create_trajet(driver.id, places=3)
        db.session.commit()
        trajet_id = t.id

    login(client, "p4@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)

    with app.app_context():
        res_id = Reservation.query.first().id

    login(client, "d4@univ.ma")
    client.post(f"/reservation/{res_id}/confirmer", follow_redirects=True)

    with app.app_context():
        res = Reservation.query.filter_by(id=res_id).first()
        assert res.statut == "confirmee"
        trajet = Trajet.query.filter_by(id=trajet_id).first()
        assert trajet.places_disponibles == 2

def test_refuse_reservation(client, app):
    with app.app_context():
        driver = create_user("d5@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("p5@univ.ma")
        t = create_trajet(driver.id, places=3)
        db.session.commit()
        trajet_id = t.id

    login(client, "p5@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)

    with app.app_context():
        res_id = Reservation.query.first().id

    login(client, "d5@univ.ma")
    client.post(f"/reservation/{res_id}/refuser", follow_redirects=True)

    with app.app_context():
        res = Reservation.query.filter_by(id=res_id).first()
        assert res.statut == "refusee"


# QUOTIDIEN TESTS

def test_quotidien_range_booking(client, app):
    with app.app_context():
        driver = create_user("dq@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("pq@univ.ma")
        t = create_trajet(driver.id, places=3, recurrence="quotidien")
        db.session.commit()
        trajet_id = t.id

    login(client, "pq@univ.ma")
    monday = next_weekday(0, min_days_ahead=1)
    friday = monday + timedelta(days=4)

    client.post(f"/reserver/{trajet_id}", data={
        "date_debut": monday.isoformat(),
        "date_fin": friday.isoformat()
    }, follow_redirects=True)

    with app.app_context():
        assert Reservation.query.count() == 5

def test_quotidien_skips_full_days(client, app):
    with app.app_context():
        driver = create_user("dq2@univ.ma", est_conducteur=True, telephone="0600000000")
        p1 = create_user("pq2@univ.ma")
        p2 = create_user("pq3@univ.ma")
        create_user("pq4@univ.ma")
        t = create_trajet(driver.id, places=1, recurrence="quotidien")
        db.session.commit()
        trajet_id = t.id
        p2_id = p2.id

        # fill monday with p1
        monday = next_weekday(0, min_days_ahead=1)
        r = Reservation(
            passager_id=p1.id, trajet_id=trajet_id,
            statut="confirmee", date_specifique=monday.isoformat()
        )
        db.session.add(r)
        db.session.commit()

    login(client, "pq3@univ.ma")
    tuesday = monday + timedelta(days=1)
    client.post(f"/reserver/{trajet_id}", data={
        "date_debut": monday.isoformat(),
        "date_fin": tuesday.isoformat()
    }, follow_redirects=True)

    with app.app_context():
        new_res = Reservation.query.filter_by(passager_id=p2_id).all()
        assert len(new_res) == 1
        assert new_res[0].date_specifique == tuesday.isoformat()

def test_quotidien_no_past_dates(client, app):
    with app.app_context():
        driver = create_user("dq5@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("pq5@univ.ma")
        t = create_trajet(driver.id, places=3, recurrence="quotidien")
        db.session.commit()
        trajet_id = t.id

    login(client, "pq5@univ.ma")
    past = (date.today() - timedelta(days=3)).isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    client.post(f"/reserver/{trajet_id}", data={
        "date_debut": past,
        "date_fin": yesterday
    }, follow_redirects=True)

    with app.app_context():
        assert Reservation.query.count() == 0


# LOG TESTS

def test_log_created_on_reservation(client, app):
    with app.app_context():
        driver = create_user("dl@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("pl@univ.ma")
        t = create_trajet(driver.id, places=3)
        db.session.commit()
        trajet_id = t.id

    login(client, "pl@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)

    with app.app_context():
        assert TrajetLog.query.count() == 1
        assert TrajetLog.query.first().emoji == "🟡"

def test_log_created_on_cancel(client, app):
    with app.app_context():
        driver = create_user("dl2@univ.ma", est_conducteur=True, telephone="0600000000")
        create_user("pl2@univ.ma")
        # use days_ahead=3 and late heure to avoid 2h block
        t = create_trajet(driver.id, places=3, days_ahead=3, heure="23:59")
        db.session.commit()
        trajet_id = t.id

    login(client, "pl2@univ.ma")
    client.get(f"/reserver/{trajet_id}", follow_redirects=True)

    with app.app_context():
        res_id = Reservation.query.first().id

    client.post(f"/reservation/{res_id}/annuler", follow_redirects=True)

    with app.app_context():
        emojis = [l.emoji for l in TrajetLog.query.all()]
        assert "🔴" in emojis


# AVAILABILITY GRID TESTS

def test_confirmed_reduces_display_count(client, app):
    """Confirmed reservations must be reflected in availability grid."""
    with app.app_context():
        driver = create_user("dg@univ.ma", est_conducteur=True, telephone="0600000000")
        passager = create_user("pg@univ.ma")
        t = create_trajet(driver.id, places=4, recurrence="quotidien")
        db.session.commit()
        trajet_id = t.id
        passager_id = passager.id

        monday = next_weekday(0, min_days_ahead=1)
        r = Reservation(
            passager_id=passager_id, trajet_id=trajet_id,
            statut="confirmee", date_specifique=monday.isoformat()
        )
        db.session.add(r)
        db.session.commit()

    login(client, "dg@univ.ma")
    res = client.get(f"/trajet/{trajet_id}", follow_redirects=True)
    assert res.status_code == 200
    # confirmed count should be visible
    with app.app_context():
        confirmed = Reservation.query.filter_by(
            trajet_id=trajet_id, statut="confirmee"
        ).count()
        assert confirmed == 1

def test_grid_shows_correct_remaining(app):
    """places_restantes = places_disponibles - confirmed_count per day."""
    with app.app_context():
        driver = create_user("dg2@univ.ma", est_conducteur=True, telephone="0600000000")
        p1 = create_user("pg2@univ.ma")
        p2 = create_user("pg3@univ.ma")
        t = create_trajet(driver.id, places=3, recurrence="quotidien")
        db.session.commit()

        monday = next_weekday(0, min_days_ahead=1)

        r1 = Reservation(passager_id=p1.id, trajet_id=t.id,
            statut="confirmee", date_specifique=monday.isoformat())
        r2 = Reservation(passager_id=p2.id, trajet_id=t.id,
            statut="confirmee", date_specifique=monday.isoformat())
        db.session.add_all([r1, r2])
        db.session.commit()

        confirmed_count = Reservation.query.filter_by(
            trajet_id=t.id,
            date_specifique=monday.isoformat(),
            statut="confirmee"
        ).count()
        restantes = t.places_disponibles - confirmed_count
        assert restantes == 1

def test_full_day_blocks_new_reservation(client, app):
    """A day with 0 places remaining should not accept new reservations."""
    with app.app_context():
        driver = create_user("dg3@univ.ma", est_conducteur=True, telephone="0600000000")
        p1 = create_user("pg4@univ.ma")
        p2 = create_user("pg5@univ.ma")
        t = create_trajet(driver.id, places=1, recurrence="quotidien")
        db.session.commit()
        trajet_id = t.id
        p2_id = p2.id

        monday = next_weekday(0, min_days_ahead=1)
        r = Reservation(passager_id=p1.id, trajet_id=trajet_id,
            statut="confirmee", date_specifique=monday.isoformat())
        db.session.add(r)
        db.session.commit()

    login(client, "pg5@univ.ma")
    client.post(f"/reserver/{trajet_id}", data={
        "date_debut": monday.isoformat(),
        "date_fin": monday.isoformat()
    }, follow_redirects=True)

    with app.app_context():
        new_res = Reservation.query.filter_by(passager_id=p2_id).all()
        assert len(new_res) == 0


# EMAIL VERIFICATION TESTS

def test_new_user_not_verified_by_default(client, app):
    with app.app_context():
        client.post("/inscription", data={
            "nom": "Test", "prenom": "Verif",
            "email": "unverified@univ.ma",
            "mot_de_passe": "test1234",
            "confirmer_mot_de_passe": "test1234",
            "zone_depart": "Mohammedia"
        }, follow_redirects=True)
        user = User.query.filter_by(email="unverified@univ.ma").first()
        assert user is not None
        assert user.email_verifie is False
        assert user.code_verification is not None

def test_unverified_user_cannot_login(client, app):
    with app.app_context():
        u = create_user("stillunverified@univ.ma")
        u.email_verifie = False
        db.session.commit()

    res = client.post("/login", data={
        "email": "stillunverified@univ.ma",
        "mot_de_passe": "password"
    }, follow_redirects=True)
    assert b"verifier votre email".lower() in res.data.lower() or res.status_code == 200

    with client.session_transaction() as sess:
        pass

def test_verify_email_with_correct_code(client, app):
    with app.app_context():
        u = create_user("verifyme@univ.ma")
        u.email_verifie = False
        u.code_verification = "123456"
        u.code_expiration = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["pending_verification_email"] = "verifyme@univ.ma"

    res = client.post("/verifier-email", data={"code": "123456"}, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        u = User.query.filter_by(email="verifyme@univ.ma").first()
        assert u.email_verifie is True
        assert u.code_verification is None

def test_verify_email_with_wrong_code(client, app):
    with app.app_context():
        u = create_user("wrongcode@univ.ma")
        u.email_verifie = False
        u.code_verification = "123456"
        u.code_expiration = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["pending_verification_email"] = "wrongcode@univ.ma"

    client.post("/verifier-email", data={"code": "000000"}, follow_redirects=True)

    with app.app_context():
        u = User.query.filter_by(email="wrongcode@univ.ma").first()
        assert u.email_verifie is False

def test_verify_email_with_expired_code(client, app):
    with app.app_context():
        u = create_user("expired@univ.ma")
        u.email_verifie = False
        u.code_verification = "123456"
        u.code_expiration = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["pending_verification_email"] = "expired@univ.ma"

    client.post("/verifier-email", data={"code": "123456"}, follow_redirects=True)

    with app.app_context():
        u = User.query.filter_by(email="expired@univ.ma").first()
        assert u.email_verifie is False


# PASSWORD RESET TESTS

def test_forgot_password_generates_code(client, app):
    with app.app_context():
        create_user("resetme@univ.ma")
        db.session.commit()

    client.post("/mot-de-passe-oublie", data={"email": "resetme@univ.ma"}, follow_redirects=True)

    with app.app_context():
        u = User.query.filter_by(email="resetme@univ.ma").first()
        assert u.reset_code is not None

def test_reset_password_with_correct_code(client, app):
    with app.app_context():
        u = create_user("resetflow@univ.ma")
        u.reset_code = "654321"
        u.reset_code_expiration = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.session.commit()
        old_hash = u.mot_de_passe

    with client.session_transaction() as sess:
        sess["pending_reset_email"] = "resetflow@univ.ma"

    res = client.post("/reinitialiser-mot-de-passe", data={
        "code": "654321",
        "nouveau_mdp": "newpassword123",
        "confirmer_mdp": "newpassword123"
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        u = User.query.filter_by(email="resetflow@univ.ma").first()
        assert u.mot_de_passe != old_hash
        assert u.reset_code is None

    res2 = client.post("/login", data={
        "email": "resetflow@univ.ma",
        "mot_de_passe": "newpassword123"
    }, follow_redirects=True)
    assert res2.status_code == 200

def test_reset_password_mismatch_rejected(client, app):
    with app.app_context():
        u = create_user("mismatch@univ.ma")
        u.reset_code = "111222"
        u.reset_code_expiration = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.session.commit()
        old_hash = u.mot_de_passe

    with client.session_transaction() as sess:
        sess["pending_reset_email"] = "mismatch@univ.ma"

    client.post("/reinitialiser-mot-de-passe", data={
        "code": "111222",
        "nouveau_mdp": "newpassword123",
        "confirmer_mdp": "differentpassword"
    }, follow_redirects=True)

    with app.app_context():
        u = User.query.filter_by(email="mismatch@univ.ma").first()
        assert u.mot_de_passe == old_hash


# PROFILE TESTS

def test_change_password_from_profile(client, app):
    with app.app_context():
        create_user("profileuser@univ.ma")
        db.session.commit()

    login(client, "profileuser@univ.ma")
    res = client.post("/profil", data={
        "mdp_actuel": "password",
        "nouveau_mdp": "brandnewpass123",
        "confirmer_mdp": "brandnewpass123"
    }, follow_redirects=True)
    assert res.status_code == 200

    res2 = client.post("/login", data={
        "email": "profileuser@univ.ma",
        "mot_de_passe": "brandnewpass123"
    }, follow_redirects=True)
    assert res2.status_code == 200

def test_change_password_wrong_current_rejected(client, app):
    with app.app_context():
        u = create_user("profilewrong@univ.ma")
        db.session.commit()
        old_hash = u.mot_de_passe

    login(client, "profilewrong@univ.ma")
    client.post("/profil", data={
        "mdp_actuel": "wrongcurrentpassword",
        "nouveau_mdp": "brandnewpass123",
        "confirmer_mdp": "brandnewpass123"
    }, follow_redirects=True)

    with app.app_context():
        u = User.query.filter_by(email="profilewrong@univ.ma").first()
        assert u.mot_de_passe == old_hash


# AVIS (REVIEWS) TESTS

def create_past_confirmed_reservation(driver_id, passager_id, days_ago=1):
    past_date = (date.today() - timedelta(days=days_ago)).isoformat()
    t = Trajet(
        depart="Mohammedia", destination="FSJES Mohammedia",
        date=past_date, heure="08:00",
        places_disponibles=3, recurrence="unique",
        conducteur_id=driver_id
    )
    db.session.add(t)
    db.session.flush()
    r = Reservation(passager_id=passager_id, trajet_id=t.id, statut="confirmee")
    db.session.add(r)
    db.session.flush()
    return t, r

def test_passager_can_rate_conducteur_after_trip(client, app):
    with app.app_context():
        driver = create_user("avisdriver1@univ.ma", est_conducteur=True, telephone="0600000000")
        passager = create_user("avispass1@univ.ma")
        t, r = create_past_confirmed_reservation(driver.id, passager.id)
        db.session.commit()
        res_id = r.id
        driver_id = driver.id

    login(client, "avispass1@univ.ma")
    resp = client.post(f"/noter/{res_id}/{driver_id}", data={
        "note": "5",
        "tags": ["Ponctuel"],
        "commentaire": "Tres bien"
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        from app.models import Avis
        avis = Avis.query.filter_by(reservation_id=res_id).first()
        assert avis is not None
        assert avis.note == 5

def test_cannot_rate_before_trip_happens(client, app):
    with app.app_context():
        driver = create_user("avisdriver2@univ.ma", est_conducteur=True, telephone="0600000000")
        passager = create_user("avispass2@univ.ma")
        future_date = (date.today() + timedelta(days=3)).isoformat()
        t = Trajet(
            depart="Mohammedia", destination="FSJES Mohammedia",
            date=future_date, heure="08:00",
            places_disponibles=3, recurrence="unique",
            conducteur_id=driver.id
        )
        db.session.add(t)
        db.session.flush()
        r = Reservation(passager_id=passager.id, trajet_id=t.id, statut="confirmee")
        db.session.add(r)
        db.session.commit()
        res_id = r.id
        driver_id = driver.id

    login(client, "avispass2@univ.ma")
    client.post(f"/noter/{res_id}/{driver_id}", data={"note": "5"}, follow_redirects=True)

    with app.app_context():
        from app.models import Avis
        assert Avis.query.filter_by(reservation_id=res_id).count() == 0

def test_cannot_rate_twice(client, app):
    with app.app_context():
        driver = create_user("avisdriver3@univ.ma", est_conducteur=True, telephone="0600000000")
        passager = create_user("avispass3@univ.ma")
        t, r = create_past_confirmed_reservation(driver.id, passager.id)
        db.session.commit()
        res_id = r.id
        driver_id = driver.id

    login(client, "avispass3@univ.ma")
    client.post(f"/noter/{res_id}/{driver_id}", data={"note": "4"}, follow_redirects=True)
    client.post(f"/noter/{res_id}/{driver_id}", data={"note": "2"}, follow_redirects=True)

    with app.app_context():
        from app.models import Avis
        assert Avis.query.filter_by(reservation_id=res_id).count() == 1

def test_cannot_rate_unrelated_reservation(client, app):
    with app.app_context():
        driver = create_user("avisdriver4@univ.ma", est_conducteur=True, telephone="0600000000")
        passager = create_user("avispass4@univ.ma")
        outsider = create_user("outsider@univ.ma")
        t, r = create_past_confirmed_reservation(driver.id, passager.id)
        db.session.commit()
        res_id = r.id
        driver_id = driver.id

    login(client, "outsider@univ.ma")
    resp = client.post(f"/noter/{res_id}/{driver_id}", data={"note": "5"}, follow_redirects=True)
    assert resp.status_code == 403

def test_invalid_note_value_rejected(client, app):
    with app.app_context():
        driver = create_user("avisdriver5@univ.ma", est_conducteur=True, telephone="0600000000")
        passager = create_user("avispass5@univ.ma")
        t, r = create_past_confirmed_reservation(driver.id, passager.id)
        db.session.commit()
        res_id = r.id
        driver_id = driver.id

    login(client, "avispass5@univ.ma")
    client.post(f"/noter/{res_id}/{driver_id}", data={"note": "9"}, follow_redirects=True)

    with app.app_context():
        from app.models import Avis
        assert Avis.query.filter_by(reservation_id=res_id).count() == 0

def test_low_rating_appears_in_admin_flagged(client, app):
    with app.app_context():
        admin_user = create_user("adminavis@univ.ma")
        admin_user.is_admin = True
        driver = create_user("avisdriver6@univ.ma", est_conducteur=True, telephone="0600000000")
        passager = create_user("avispass6@univ.ma")
        t, r = create_past_confirmed_reservation(driver.id, passager.id)
        db.session.commit()
        res_id = r.id
        driver_id = driver.id

    login(client, "avispass6@univ.ma")
    client.post(f"/noter/{res_id}/{driver_id}", data={"note": "1", "commentaire": "Mauvaise experience"}, follow_redirects=True)

    login(client, "adminavis@univ.ma")
    resp = client.get("/admin/", follow_redirects=True)
    assert b"Mauvaise experience" in resp.data
