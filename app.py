import io
import sqlite3
import os
from datetime import datetime, timedelta
import csv
import secrets
import logging
from functools import wraps
from shapely.geometry import LineString, Point
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask import  jsonify, send_from_directory, make_response, render_template, redirect, url_for
from flask import flash
from flask import request, session
from flask import Flask, json, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db,close_db
from utils.emails import (
    trimite_email_resetare,
    trimite_email_confirmare_abonament,
    trimite_email_reminder_expirare
)


logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
@app.teardown_appcontext
def close_connection(exception):
    close_db()


app.config['SECRET_KEY'] = 'tine_o_secret_bine'
DATABASE = 'database.db'
limiter = Limiter(app)
load_dotenv()
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
UPLOAD_FOLDER = os.path.join("static", "snapshots")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
    with open("timicampark_zone_eticheta_final.json", "r", encoding="utf-8") as f:
        timicampark_zones = json.load(f)
except Exception as e:
    print(f"Eroare la încărcarea fișierului JSON: {e}")
    timicampark_zones = []

# Caută zona pentru o adresă
def get_timicampark_zone(address, buffer_size=0.001):  # ~50 metri buffer

    geolocator = Nominatim(user_agent="timicampark-checker")
    location = geolocator.geocode(address)

    if not location:
        print("Adresa nu a fost localizată.")
        return "Adresa nu a putut fi localizată."

    # Punctul obținut din geolocalizare
    point = Point(location.longitude, location.latitude)
    print(f"Adresă localizată la: ({location.latitude}, {location.longitude})")

    for zona in timicampark_zones:
        try:
            # Conversie lat/lon -> lon,lat pentru Shapely
            coordonate = [(lon, lat) for lat, lon in zona["coordonate"]]

            if len(coordonate) < 2:
                print(f"Zona {zona['eticheta']} are mai puțin de 2 puncte. Sar peste.")
                continue

            line = LineString(coordonate)
            zona_buffer = line.buffer(buffer_size)

            distance = zona_buffer.distance(point)
            print(f"{zona['eticheta']} (zona {zona['zona']}) - distanță: {distance:.6f}")

            if zona_buffer.contains(point):
                print(f"Match în {zona['eticheta']} (zona {zona['zona']})")
                return f"Adresa se află în zona TimiCamPark: <strong>{zona['zona']}</strong>"

        except Exception as e:
            print(f"Eroare la zona {zona.get('eticheta')}: {e}")

    return "ℹAdresa nu se află într-o zonă TimiCamPark."


@app.route('/verifica-zona', methods=['GET', 'POST'])
def verifica_zona():
    rezultat = None
    if request.method == 'POST':
        adresa = request.form.get('adresa')
        if adresa:
            rezultat = get_timicampark_zone(adresa)
    return render_template('verifica_zona.html', rezultat=rezultat)


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

@app.cli.command('initdb')
def initdb_command():
    """Initialize the database."""
    init_db()
    print('Initialized the database.')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def salveaza_amenda(numar_inmatriculare, motiv, snapshot_path, zona):
    db = get_db()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute('''
        INSERT INTO Amenzi (numar_inmatriculare, timestamp, motiv, snapshot_path, zona)
        VALUES (?, ?, ?, ?, ?)
    ''', (numar_inmatriculare, timestamp, motiv, snapshot_path, zona))
    db.commit()
    #db.close()


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login'))

        db = get_db()
        user = db.execute(
            'SELECT este_admin FROM Utilizatori WHERE id_utilizator = ?',
            (session['user_id'],)
        ).fetchone()
        #db.close()

        if not user or not user['este_admin']:
            flash('Acces interzis: doar pentru administratori.', 'danger')
            return redirect(url_for('hello'))

        return f(*args, **kwargs)
    return decorated_function


@limiter.limit("5 per minute")
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        nume = request.form.get('nume')
        email = request.form.get('email')
        parola = request.form.get('parola')
        db = get_db()

        if not nume:
            error = 'Numele este obligatoriu.'
        elif not email:
            error = 'Emailul este obligatoriu.'
        elif not parola:
            error = 'Parola este obligatorie.'
        elif len(parola) < 8 or not any(c.isupper() for c in parola) or not any(c.isdigit() for c in parola):
            error = 'Parola trebuie să aibă minim 8 caractere, o literă mare și un număr.'
        elif db.execute(
            'SELECT id_utilizator FROM Utilizatori WHERE email = ?', (email,)
        ).fetchone() is not None:
            error = f'Utilizatorul cu emailul {email} este deja înregistrat.'

        if error is None:
            parola_hash = generate_password_hash(parola)
            db.execute(
                'INSERT INTO Utilizatori (nume, email, parola) VALUES (?, ?, ?)',
                (nume, email, parola_hash)
            )
            db.commit()
            return redirect(url_for('login'))

    return render_template('register.html', error=error)

@limiter.limit("5 per minute")
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        parola = request.form.get('parola')
        db = get_db()
        user = db.execute(
            'SELECT * FROM Utilizatori WHERE email = ?', (email,)
        ).fetchone()
        #db.close()

        if user is None:
            error = 'Email incorect.'
        elif not check_password_hash(user['parola'], parola):
            error = 'Parolă incorectă.'
        else:
            session.clear()
            session['user_id'] = user['id_utilizator']
            if 'este_admin' and user['este_admin']:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('hello'))

    return render_template('login.html', error=error)



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('hello'))

@app.route('/cumpara_abonament', methods=['GET', 'POST'])
@login_required
def cumpara_abonament():
    db = get_db()
    error = None

    if request.method == 'POST':
        numar_inmatriculare = request.form.get('numar_inmatriculare', '').strip().upper()
        zona = request.form.get('zona')
        tip_abonament = request.form.get('tip_abonament')
        durata_ore = request.form.get('durata_ore')
        durata_zile = request.form.get('durata_zile')
        data_inceput_str = request.form.get('data_inceput')

        try:
            # Determină durata în funcție de tipul abonamentului
            if tip_abonament == 'ora':
                durata = int(durata_ore or 0)
            elif tip_abonament == 'zi':
                durata = int(durata_zile or 0)
            else:
                durata = 0

            if durata <= 0:
                raise ValueError("Durata trebuie să fie mai mare ca 0.")

            data_inceput = datetime.fromisoformat(data_inceput_str)

            # Calculează data de sfârșit și prețul în funcție de zona și tip
            if tip_abonament == 'ora':
                data_sfarsit = data_inceput + timedelta(hours=durata)
                pret = durata * (4 if zona == 'Zona 1' else 2 if zona == 'Zona 2' else 1 if zona == 'Zona 3' else 0.5)
            elif tip_abonament == 'zi':
                data_sfarsit = data_inceput + timedelta(days=durata)
                pret = durata * (40 if zona == 'Zona 1' else 20 if zona == 'Zona 2' else 10 if zona == 'Zona 3' else 5)
            else:
                raise ValueError("Tip de abonament invalid")

            # Inserare în Abonamente
            cursor = db.execute('''
                INSERT INTO Abonamente (id_utilizator, numar_inmatriculare, zona, tip_abonament, durata,
                    data_inceput, data_sfarsit, pret, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['user_id'], numar_inmatriculare, zona, tip_abonament, durata,
                data_inceput, data_sfarsit, pret, 'activ'
            ))
            id_abonament = cursor.lastrowid

            # Inserare în Tranzacții (cu metodă și status)
            db.execute('''
                INSERT INTO Tranzactii (id_utilizator, id_abonament, suma, data_tranzactie, metoda_plata, status_tranzactie)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session['user_id'], id_abonament, pret, datetime.now(), 'card', 'succes'
            ))

            # Trimite email de confirmare
            user_email = db.execute(
                'SELECT email FROM Utilizatori WHERE id_utilizator = ?', (session['user_id'],)
            ).fetchone()['email']

            trimite_email_confirmare_abonament(
                user_email,
                {
                    "numar": numar_inmatriculare,
                    "zona": zona,
                    "inceput": data_inceput,
                    "sfarsit": data_sfarsit
                }
            )

            db.commit()
            flash('Abonament achiziționat cu succes!', 'success')
            return redirect(url_for('abonamentele_mele'))

        except Exception as e:
            error = f"Eroare: {e}"

    return render_template('cumpara_abonament.html', error=error)


def actualizeaza_status_abonamente():
    db = get_db()
    now = datetime.now()
    cursor = db.cursor()
    cursor.execute("UPDATE Abonamente SET status = 'expirat' WHERE data_sfarsit < ?", (now,))
    cursor.execute("UPDATE Abonamente SET status = 'activ' WHERE data_inceput <= ? AND data_sfarsit >= ?", (now,now))
    db.commit()
    #db.close()
    logging.debug("S-a executat actualizarea statusului abonamentelor.")


@app.route('/abonamentele_mele', methods=['GET', 'POST'])
@login_required
def abonamentele_mele():
    actualizeaza_status_abonamente()
    logging.debug(f"request.form: {request.form}")
    db = get_db()
    status_filter = request.form.get('status_filter')
    logging.debug(f"status_filter: {status_filter}")
    query = 'SELECT * FROM Abonamente WHERE id_utilizator = ? ORDER BY data_inceput DESC'
    params = (session['user_id'],)

    if status_filter == 'activ':
        query = 'SELECT * FROM Abonamente WHERE id_utilizator = ? AND status = ? ORDER BY data_inceput DESC'
        params = (session['user_id'], 'activ')
        logging.debug("Filtrul activ este aplicat.")
    elif status_filter == 'expirat':
        query = 'SELECT * FROM Abonamente WHERE id_utilizator = ? AND status = ? ORDER BY data_inceput DESC'
        params = (session['user_id'], 'expirat')
        logging.debug("Filtrul expirat este aplicat.")
    elif status_filter == 'viitor':
        query = 'SELECT * FROM Abonamente WHERE id_utilizator = ? AND data_inceput > ? ORDER BY data_inceput DESC'
        params = (session['user_id'], datetime.now())
        logging.debug("Filtrul viitor este aplicat.")
    elif status_filter == 'toate':
        query = 'SELECT * FROM Abonamente WHERE id_utilizator = ? ORDER BY data_inceput DESC'
        params = (session['user_id'],)
        logging.debug("Filtrul toate este aplicat.")

    abonamente_rows = db.execute(query, params).fetchall()
    abonamente = []

    for row in abonamente_rows:
        abonament = dict(row)

        try:
            abonament['data_inceput'] = datetime.fromisoformat(abonament['data_inceput']) \
                if abonament['data_inceput'] else None
        except (TypeError, ValueError):
            abonament['data_inceput'] = None

        try:
            abonament['data_sfarsit'] = datetime.fromisoformat(abonament['data_sfarsit']) \
                if abonament['data_sfarsit'] else None
        except (TypeError, ValueError):
            abonament['data_sfarsit'] = None

        try:
            abonament['data_achizitie'] = datetime.fromisoformat(abonament['data_achizitie']) \
                if abonament['data_achizitie'] else None
        except (TypeError, ValueError):
            abonament['data_achizitie'] = None

        # Determine and set display_status
        now = datetime.now()
        if abonament['data_inceput'] and abonament['data_inceput'] > now:
            display_status = 'Viitor'
        elif abonament['data_sfarsit'] and abonament['data_sfarsit'] < now:
            display_status = 'Expirat'
        else:
            display_status = 'Activ'

        abonament['display_status'] = display_status
        abonamente.append(abonament)

    print(f"Abonamente: {abonamente}")
    print(f"Status Filter: {status_filter}")
    return render_template('abonamentele_mele.html', abonamente=abonamente, now=datetime.now(), status_filter=status_filter, datetime=datetime)



@app.route('/verifica_abonament', methods=['GET', 'POST'])
def verifica_abonament():
    abonamente_active = []
    if request.method == 'POST':
        numar_inmatriculare = request.form['numar_inmatriculare'].strip().upper()
        if numar_inmatriculare:
            db = get_db()
            abonamente_active_rows = db.execute(
                'SELECT * FROM Abonamente WHERE numar_inmatriculare = ? AND status = ? ORDER BY data_inceput DESC',
                (numar_inmatriculare, 'activ')
            ).fetchall()

            for row in abonamente_active_rows:
                abonament = dict(row)
                abonament['data_inceput'] = datetime.fromisoformat(abonament['data_inceput'])
                abonament['data_sfarsit'] = datetime.fromisoformat(abonament['data_sfarsit'])

                # Aici calculăm statusul real
                now = datetime.now()
                if abonament['data_inceput'] > now:
                    abonament['display_status'] = 'Viitor'
                elif abonament['data_sfarsit'] < now:
                    abonament['display_status'] = 'Expirat'
                else:
                    abonament['display_status'] = 'Activ'

                abonamente_active.append(abonament)

            #db.close()
    return render_template('verifica_abonament.html', abonamente=abonamente_active)



@app.route('/notificare_expirare')
def notificare_expirare():
    db = get_db()
    now = datetime.now()
    expira_in_15_min = now + timedelta(minutes=15)
    abonamente_expirand = db.execute(
        'SELECT a.numar_inmatriculare, a.data_sfarsit, u.email '
        'FROM Abonamente a JOIN Utilizatori u ON a.id_utilizator = u.id_utilizator '
        'WHERE a.status = ? AND a.data_sfarsit BETWEEN ? AND ?',
        ('activ', now, expira_in_15_min)
    ).fetchall()
    #db.close()

    notificari_trimise = []
    for abonament in abonamente_expirand:
        numar_inmatriculare = abonament['numar_inmatriculare']
        data_sfarsit = abonament['data_sfarsit']
        email_destinatar = abonament['email']
        try:
            trimite_email_reminder_expirare(email_destinatar, numar_inmatriculare, data_sfarsit)
            notificari_trimise.append(f"Notificare de expirare trimisă pentru {numar_inmatriculare} către {email_destinatar}")
        except Exception as e:
         notificari_trimise.append(f"Eroare la trimiterea notificării pentru {numar_inmatriculare} către {email_destinatar}: {e}")


    return "<br>".join(notificari_trimise) if notificari_trimise else "Niciun abonament nu expiră în următoarele 15 minute."


@app.route('/reset_parola', methods=['GET', 'POST'])
def reset_parola_request():
    if request.method == 'POST':
        email = request.form.get('email')
        db = get_db()
        user = db.execute('SELECT * FROM Utilizatori WHERE email = ?', (email,)).fetchone()
        #db.close()

        if user:
            reset_token = secrets.token_urlsafe(16)
            token_expirare = datetime.now() + timedelta(hours=1)
            db = get_db()
            db.execute(
                'UPDATE Utilizatori SET reset_token = ?, reset_token_expirare = ? WHERE email = ?',
                (reset_token, token_expirare, email)
            )
            db.commit()
            #db.close()

            reset_link = url_for('reset_parola_confirm', token=reset_token, _external=True)
            logging.debug(f"Link de resetare generat: {reset_link}")

            try:
                trimite_email_resetare(email, reset_link)
                flash('Un link de resetare a fost trimis pe adresa de email.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                logging.error(f"Eroare la trimiterea emailului de resetare: {e}")
                flash('Eroare la trimiterea emailului de resetare. Vă rugăm să încercați din nou.', 'danger')


    return render_template('reset_parola_request.html')


@app.route('/reset_parola/<token>', methods=['GET', 'POST'])
def reset_parola_confirm(token):
    db = get_db()
    user = db.execute('SELECT * FROM Utilizatori WHERE reset_token = ?', (token,)).fetchone()
    #db.close()

    if not user:
        flash('Link de resetare invalid sau expirat.', 'danger')
        return redirect(url_for('login'))

    if datetime.now() > datetime.fromisoformat(user['reset_token_expirare']):
        flash('Link-ul de resetare a expirat. Vă rugăm să solicitați din nou resetarea parolei.', 'danger')
        return redirect(url_for('reset_parola_request'))


    if request.method == 'POST':
        parola = request.form.get('parola')
        confirm_parola = request.form.get('confirm_parola')

        if not parola:
            flash('Parola este obligatorie.', 'danger')
        elif parola != confirm_parola:
            flash('Parolele nu se potrivesc.', 'danger')
        else:
            parola_hash = generate_password_hash(parola)
            db = get_db()
            db.execute(
                'UPDATE Utilizatori SET parola = ?, reset_token = NULL, reset_token_expirare = NULL WHERE id_utilizator = ?',
                (parola_hash, user['id_utilizator'])
            )
            db.commit()
            #db.close()
            flash('Parola a fost resetată cu succes. Vă puteți autentifica acum.', 'success')
            return redirect(url_for('login'))

    return render_template('reset_parola_confirm.html', token=token)


@app.route('/')
@login_required
def hello():
    db = get_db()
    user = db.execute('SELECT nume FROM Utilizatori WHERE id_utilizator = ?', (session['user_id'],)).fetchone()
    #db.close()
    nume_utilizator = user['nume'] if user else 'Utilizator'
    return render_template('hello.html', nume=nume_utilizator)

@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_dashboard():
    db = get_db()

    zona_filter = request.form.get('zona')
    status_filter = request.form.get('status')

    # Filtrare dinamică
    query = 'SELECT * FROM Abonamente WHERE 1=1'
    params = []

    if zona_filter:
        query += ' AND zona = ?'
        params.append(zona_filter)
    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)

    query += ' ORDER BY data_inceput DESC'
    abonamente = db.execute(query, params).fetchall()

    utilizatori = db.execute('SELECT id_utilizator, nume, email, este_admin FROM Utilizatori').fetchall()
    #db.close()

    return render_template('admin_dashboard.html', utilizatori=utilizatori, abonamente=abonamente)


@app.route('/admin/add_user', methods=['GET', 'POST'])
@admin_required
def add_user():
    error = None
    if request.method == 'POST':
        nume = request.form.get('nume')
        email = request.form.get('email')
        parola = request.form.get('parola')
        este_admin = int(request.form.get('este_admin', 0))

        if not nume or not email or not parola:
            error = 'Toate câmpurile sunt obligatorii.'
        else:
            db = get_db()
            exista = db.execute('SELECT id_utilizator FROM Utilizatori WHERE email = ?', (email,)).fetchone()
            if exista:
                error = 'Există deja un utilizator cu acest email.'
            else:
                parola_hash = generate_password_hash(parola)
                db.execute(
                    'INSERT INTO Utilizatori (nume, email, parola, este_admin) VALUES (?, ?, ?, ?)',
                    (nume, email, parola_hash, este_admin)
                )
                db.commit()
                #db.close()
                flash('Utilizator adăugat cu succes.', 'success')
                return redirect(url_for('admin_dashboard'))
            #db.close()
    return render_template('admin_add_user.html', error=error)

@app.route('/admin_add_abonament', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_abonament():
    db = get_db()
    error = None

    if request.method == 'POST':
        id_utilizator = request.form.get('id_utilizator')
        numar_inmatriculare = request.form.get('numar_inmatriculare').strip().upper()
        zona = request.form.get('zona')
        tip_abonament = request.form.get('tip_abonament')
        durata = int(request.form.get('durata'))
        data_inceput_str = request.form.get('data_inceput')

        try:
            data_inceput = datetime.fromisoformat(data_inceput_str)
            if tip_abonament == 'ora':
                data_sfarsit = data_inceput + timedelta(hours=durata)
                pret = durata * (4 if zona == 'Zona 1' else 2 if zona == 'Zona 2' else 1 if zona == 'Zona 3' else 0.5)
            elif tip_abonament == 'zi':
                data_sfarsit = data_inceput + timedelta(days=durata)
                pret = durata * (40 if zona == 'Zona 1' else 20 if zona == 'Zona 2' else 10 if zona == 'Zona 3' else 5)
            else:
                raise ValueError("Tip de abonament invalid")

            db.execute('''
                INSERT INTO Abonamente (id_utilizator, numar_inmatriculare, zona, tip_abonament, durata,
                    data_inceput, data_sfarsit, pret, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id_utilizator, numar_inmatriculare, zona, tip_abonament, durata,
                  data_inceput, data_sfarsit, pret, 'activ'))

            db.commit()
            flash('Abonament adăugat cu succes!', 'success')
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            error = f"Eroare: {e}"

    utilizatori = db.execute('SELECT id_utilizator, nume FROM Utilizatori').fetchall()
    #db.close()
    return render_template('admin_add_abonament.html', error=error, utilizatori=utilizatori)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    db = get_db()
    try:
        db.execute('DELETE FROM Utilizatori WHERE id_utilizator = ?', (user_id,))
        db.commit()
        flash('Utilizator șters cu succes.', 'success')
    except Exception as e:
        flash(f'Eroare la ștergerea utilizatorului: {e}', 'danger')
    #finally:
    #    db.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_abonament/<int:abonament_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_abonament(abonament_id):
    db = get_db()
    try:
        db.execute('DELETE FROM Abonamente WHERE id_abonament = ?', (abonament_id,))
        db.commit()
        flash('Abonament șters cu succes.', 'success')
    except Exception as e:
        flash(f'Eroare la ștergerea abonamentului: {e}', 'danger')
    #finally:
    #    db.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_user():
    error = None
    if request.method == 'POST':
        nume = request.form.get('nume')
        email = request.form.get('email')
        parola = request.form.get('parola')
        este_admin = int(request.form.get('este_admin', 0))

        if not nume or not email or not parola:
            error = 'Toate câmpurile sunt obligatorii.'
        else:
            db = get_db()
            existing = db.execute('SELECT id_utilizator FROM Utilizatori WHERE email = ?', (email,)).fetchone()
            if existing:
                error = 'Emailul este deja folosit.'
            else:
                parola_hash = generate_password_hash(parola)
                db.execute(
                    'INSERT INTO Utilizatori (nume, email, parola, este_admin) VALUES (?, ?, ?, ?)',
                    (nume, email, parola_hash, este_admin)
                )
                db.commit()
                #db.close()
                flash('Utilizator adăugat cu succes!', 'success')
                return redirect(url_for('admin_dashboard'))

    return render_template('admin_add_user.html', error=error)

@app.route('/admin/export_abonamente')
@login_required
@admin_required
def export_abonamente():
    db = get_db()
    abonamente = db.execute('SELECT * FROM Abonamente').fetchall()
    #db.close()

    def generate_csv():
        header = abonamente[0].keys() if abonamente else []
        yield ','.join(header) + '\n'
        for row in abonamente:
            yield ','.join(str(row[key]) for key in header) + '\n'

    return Response(generate_csv(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=abonamente.csv"})

@app.route('/admin/statistici')
@login_required
@admin_required
def admin_statistici():
    db = get_db()
    total_utilizatori = db.execute('SELECT COUNT(*) FROM Utilizatori').fetchone()[0]
    total_abonamente = db.execute('SELECT COUNT(*) FROM Abonamente').fetchone()[0]
    abonamente_active = db.execute("SELECT COUNT(*) FROM Abonamente WHERE status = 'activ'").fetchone()[0]
    incasari_totale = db.execute("SELECT SUM(pret) FROM Abonamente").fetchone()[0] or 0
    #db.close()

    return render_template("admin_statistici.html",
                           total_utilizatori=total_utilizatori,
                           total_abonamente=total_abonamente,
                           abonamente_active=abonamente_active,
                           incasari_totale=incasari_totale)

@app.route('/admin/utilizator/<int:user_id>/abonamente')
@login_required
@admin_required
def admin_abonamente_utilizator(user_id):
    db = get_db()
    utilizator = db.execute('SELECT nume FROM Utilizatori WHERE id_utilizator = ?', (user_id,)).fetchone()
    abonamente = db.execute('SELECT * FROM Abonamente WHERE id_utilizator = ?', (user_id,)).fetchall()
    #db.close()

    return render_template('admin_abonamente_utilizator.html', abonamente=abonamente, utilizator=utilizator)

@app.route('/anpr_detectie', methods=['POST'])
def anpr_detectie():
    try:
        nr_inmatriculare = request.form.get('nr_inmatriculare')
        zona = request.form.get('zona')  # zona asociata camerei
        timestamp_str = request.form.get('timestamp')  # format: YYYY-MM-DD HH:MM:SS
        imagine = request.files.get('snapshot')

        if not all([nr_inmatriculare, zona, timestamp_str, imagine]):
            return jsonify({"error": "Date lipsă!"}), 400

        # Salvare imagine cu nume sigur + timestamp unic
        timestamp_obj = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        filename = secure_filename(f"{nr_inmatriculare}_{timestamp_obj.strftime('%Y%m%d_%H%M%S')}.jpg")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        imagine.save(filepath)

        # Calea relativă pentru baza de date
        snapshot_path = f"snapshots/{filename}"  # ← Asta va fi servită prin /static/snapshots/...

        # Verificare abonament valid la acel moment
        db = get_db()
        query = '''
            SELECT * FROM Abonamente
            WHERE numar_inmatriculare = ?
              AND zona = ?
              AND data_inceput <= ? AND data_sfarsit >= ?
              AND status = 'activ'
        '''
        abonament = db.execute(query, (nr_inmatriculare, zona, timestamp_str, timestamp_str)).fetchone()

        are_abonament = bool(abonament)

        # Salvare detecție
        db.execute('''
            INSERT INTO Detectii (numar_inmatriculare, zona, timestamp_intrare, snapshot_path, are_abonament)
            VALUES (?, ?, ?, ?, ?)
        ''', (nr_inmatriculare, zona, timestamp_str, snapshot_path, int(are_abonament)))

        db.commit()
        #db.close()

        return jsonify({"mesaj": "Detectie salvata cu succes", "abonament_valid": are_abonament}), 200

    except Exception as e:
        return jsonify({"eroare": str(e)}), 500


# Endpoint pt a servi imaginile la nevoie
@app.route('/static/snapshots/<path:filename>')
def serve_snapshot(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/admin_amenzi', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_amenzi():
    db = get_db()
    query = "SELECT * FROM Amenzi WHERE 1=1"
    params = []

    if request.method == 'POST':
        numar_inmatriculare = request.form.get('numar_inmatriculare', '').strip().upper()
        zona = request.form.get('zona', '')

        if numar_inmatriculare:
            query += " AND numar_inmatriculare LIKE ?"
            params.append(f"%{numar_inmatriculare}%")
        if zona:
            query += " AND zona = ?"
            params.append(zona)

    amenzi = db.execute(query, params).fetchall()
    return render_template('admin_amenzi.html', amenzi=amenzi)




@app.route('/admin/export_amenzi')
@login_required
@admin_required
def export_amenzi():
    db = get_db()
    amenzi = db.execute('SELECT * FROM Amenzi').fetchall()
    #db.close()

    # Pregătim răspunsul CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['ID Amenda', 'Nr. Înmatriculare', 'Timestamp', 'Motiv', 'Snapshot Path', 'Zonă'])

    # Date
    for a in amenzi:
        writer.writerow([
            a['id_amenda'],
            a['numar_inmatriculare'],
            a['timestamp'],
            a['motiv'],
            a['snapshot_path'],
            a['zona']
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=amenzi.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/admin_add_amenda', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_amenda():
    error = None
    if request.method == 'POST':
        nr = request.form.get('numar_inmatriculare').strip().upper()
        motiv = request.form.get('motiv')
        zona = request.form.get('zona')
        timestamp = datetime.now().isoformat()
        snapshot_path = request.form.get('snapshot_path')  # Exemplu: "uploads/masina123.png"

        try:
            db = get_db()
            db.execute("""
                INSERT INTO Amenzi (numar_inmatriculare, timestamp, motiv, snapshot_path, zona)
                VALUES (?, ?, ?, ?, ?)
            """, (nr, timestamp, motiv, snapshot_path, zona))
            db.commit()
            flash("Amenda a fost adăugată cu succes!", "success")
            return redirect(url_for('admin_amenzi'))
        except Exception as e:
            error = str(e)

    return render_template('admin_add_amenda.html', error=error)

@app.route('/admin/sterge_amenda/<int:id_amenda>', methods=['POST'])
@admin_required
def sterge_amenda(id_amenda):
    db = get_db()
    db.execute('DELETE FROM Amenzi WHERE id_amenda = ?', (id_amenda,))
    db.commit()
    flash('Amenda a fost ștearsă cu succes.', 'success')
    return redirect(url_for('admin_amenzi'))


if __name__ == '__main__':
    app.run(debug=True)