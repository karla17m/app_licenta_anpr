# TimiCamPark – Sistem automatizat de control al parcării în Timișoara

## Link către repository

Repository Git:  
 [https://github.com/karla17m/app_licenta_anpr]

---

##  Pași de instalare și rulare aplicație

### 1. Instalare dependințe (opțional cu `venv`)

```bash
python -m venv venv
source venv/bin/activate    # pe Linux/macOS
venv\Scripts\activate.bat   # pe Windows

pip install flask flask-wtf python-dotenv werkzeug requests pytesseract opencv-python ultralytics fuzzywuzzy python-Levenshtein geopy shapely matplotlib
```

### 2. Configurare Tesseract

- Instalează Tesseract OCR de la: https://github.com/tesseract-ocr/tesseract  
- Pe Windows: setează `pytesseract.pytesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'` în scriptul ANPR.

### 3. Configurare fișier `.env`

Crează un fișier `.env` cu următorul conținut:

```ini
SECRET_KEY=ceva_secret
SENDGRID_API_KEY=apikey
```

### 4. Inițializare bază de date

```bash
sqlite3 database.db < schema.sql
```
---

##  Lansare aplicație

### a) Pornire server Flask

```bash
python app.py
```

Aplicația pornește pe `http://127.0.0.1:5000`.

### b) Rulare ANPR local

În `anpr_client`, rulează:

```bash
python anpr_extension.py
```

Acesta va procesa imaginile din `test_images/`, va detecta numerele de înmatriculare cu YOLOv8 + OCR și va trimite automat POST-uri către ruta `/anpr_detectie`.

---

##  Funcționalități cheie

- Recunoaștere automată a numerelor de înmatriculare (YOLOv8 + Tesseract)
- Asociere automată cu zona Timpark
- Generare automată de amenzi dacă nu există abonament activ
- Rute API și interfață web (HTML + Jinja2)
- Panou admin cu export CSV, filtrare și vizualizare mașini în parcare
- Resetare parolă prin email cu token (SendGrid)
- Securitate cu CSRF, autentificare, rate-limiting, loguri admin

---

##  Observații

- Aplicația rulează complet local (Flask + ANPR), fără alte servere externe.
- ANPR-ul poate fi testat cu imaginile din `test_images/` sau cu un stream video.
- Codul este modular și poate fi extins pentru a suporta baze de date mai complexe sau autentificare OAuth.

---
