import requests
import base64
from datetime import datetime

def trimite_detectie(numar, zona, timestamp, id_camera, cale_snapshot):
    with open(cale_snapshot, "rb") as f:
        encoded = base64.b64encode(f.read()).decode('utf-8')

    headers = {"Content-Type": "application/json"}
    payload = {
        "numar_inmatriculare": numar,
        "timestamp": timestamp.isoformat(),
        "zona": zona,
        "id_camera": id_camera,
        "snapshot_base64": encoded
    }

    try:
        r = requests.post("http://127.0.0.1:5000/anpr_detectie", json=payload, headers=headers)
        print(f"[API] Răspuns Flask: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"[!] Eroare la trimitere: {e}")
