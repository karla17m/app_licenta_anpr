import os
import cv2
import pytesseract
import base64
import requests
from datetime import datetime
from ultralytics import YOLO
from fuzzywuzzy import fuzz

# Setare pytesseract
pytesseract.pytesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'  # modifică dacă e pe alt sistem

valid_judete = [
    'B', 'AB', 'AG', 'AR', 'BC', 'BH', 'BN', 'BR', 'BT', 'BV', 'BZ', 'CJ', 'CL', 'CS', 'CT',
    'CV', 'DB', 'DJ', 'GJ', 'GL', 'GR', 'HD', 'HR', 'IF', 'IL', 'IS', 'MH', 'MM', 'MS', 'NT',
    'OT', 'PH', 'SB', 'SJ', 'SM', 'SV', 'TL', 'TM', 'TR', 'VL', 'VN', 'VS'
]

def get_closest_judet(detected_prefix):
    max_score = 0
    closest_judet = None
    for judet in valid_judete:
        score = fuzz.ratio(detected_prefix.upper(), judet)
        if score > max_score:
            max_score = score
            closest_judet = judet
    return closest_judet

# YOLOv8 model
model = YOLO('best.pt')  # pune calea corectă

# Setări
BACKEND_URL = 'http://127.0.0.1:5000/anpr_detectie'
CAMERA_ID = 1
ZONA = 'Zona 1'

MIN_BOX_WIDTH = 30
MIN_BOX_HEIGHT = 10
MIN_TEXT_LENGTH = 5
CONFIDENCE_THRESHOLD = 0.4
ASPECT_RATIO_RANGE = (1.2, 6.0)
PADDING = 2

def encode_image_to_base64(img):
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

def clean_text(txt):
    return ''.join(c for c in txt if c.isalnum()).upper()

def process_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"[Eroare] Imagine invalidă: {image_path}")
        return

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_h, img_w = img_rgb.shape[:2]
    results = model.predict(img_rgb, conf=CONFIDENCE_THRESHOLD)
    detections = results[0]

    if detections.boxes is None:
        print(f"[Info] Nicio detecție în: {image_path}")
        return

    for box in detections.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        width, height = x2 - x1, y2 - y1
        aspect_ratio = width / height if height else 0

        if width < MIN_BOX_WIDTH or height < MIN_BOX_HEIGHT:
            continue
        if not (ASPECT_RATIO_RANGE[0] <= aspect_ratio <= ASPECT_RATIO_RANGE[1]):
            continue

        x1, y1 = max(0, x1 - PADDING), max(0, y1 - PADDING)
        x2, y2 = min(img_w, x2 + PADDING), min(img_h, y2 + PADDING)
        plate_crop = img_rgb[y1:y2, x1:x2]

        gray = cv2.cvtColor(plate_crop, cv2.COLOR_RGB2GRAY)
        eq = cv2.equalizeHist(gray)
        blur = cv2.GaussianBlur(eq, (3, 3), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

        # Resize pentru OCR
        resized = cv2.resize(morph, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)
        resized_orig = cv2.resize(eq, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)

        config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text1 = clean_text(pytesseract.image_to_string(resized, config=config))
        text2 = clean_text(pytesseract.image_to_string(resized_orig, config=config))

        final_text = text1 if len(text1) >= len(text2) else text2
        if len(final_text) < MIN_TEXT_LENGTH:
            continue

        # Corectare prefix județ
        prefix = final_text[:2]
        corect = get_closest_judet(prefix)
        if corect and not final_text.startswith(corect):
            final_text = corect + final_text[2:]

        timestamp = datetime.now().isoformat()
        snapshot_b64 = encode_image_to_base64(img)

        payload = {
            'numar_inmatriculare': final_text,
            'timestamp': timestamp,
            'zona': ZONA,
            'id_camera': CAMERA_ID,
            'snapshot_base64': snapshot_b64
        }

        try:
            response = requests.post(BACKEND_URL, json=payload)
            print(f"[OK] {final_text} trimis: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[Eroare] Trimitere eșuată: {e}")

# Test pe un folder local
FOLDER_TEST = 'test_images'  # modifică dacă ai alt folder

if os.path.exists(FOLDER_TEST):
    for file in os.listdir(FOLDER_TEST):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            process_image(os.path.join(FOLDER_TEST, file))
else:
    print(f"[Eroare] Folderul {FOLDER_TEST} nu există.")
