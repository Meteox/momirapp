import json
import time
import os
import requests
import subprocess
import RPi.GPIO as GPIO
from escpos.printer import Serial
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import Image
from io import BytesIO

# --- CONFIG ---
SERVER_URL = "http://85.215.219.243:5000" 
AUTH_TOKEN = "zhmwsdl<3"

PI_BASE_DIR = os.path.expanduser("~/momirapp") 
if not os.path.exists(PI_BASE_DIR):
    os.makedirs(PI_BASE_DIR)
TEMP_BMP_PATH = os.path.join(PI_BASE_DIR, "current_card.bmp")

UP_PIN, PRINT_PIN, DOWN_PIN = 11, 13, 15

# Hier sind die Kategorienamen exakt so hinterlegt, wie die Server-Ordner heißen
CATEGORIES = ["creatures", "artifacts", "battles", "enchantments", "instants", "lands", "planeswalkers", "sorceries"]
current_cat_idx = 0
current_cmc = 1
HOLD_THRESHOLD = 0.8 # Ab hier zählt es als langer Tastendruck (Toggle)

# 1. OLED Setup
try:
    serial_int = i2c(port=1, address=0x3C)
    device = ssd1306(serial_int, width=128, height=32)
    has_screen = True
except:
    has_screen = False

def update_ui(l1, l2=""):
    if has_screen:
        try:
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white")
                draw.text((5, 4), l1, fill="white")
                draw.text((5, 18), l2, fill="white")
        except: pass

# 2. Printer Setup
try:
    p = Serial(devfile='/dev/serial0', baudrate=9600, timeout=1.0)
except:
    p = None

# --- WLAN FUNKTIONEN ---
def scan_wifi():
    update_ui("WIFI SCAN", "SEARCHING...")
    try:
        result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi'])
        ssids = list(set([line for line in result.decode('utf-8').split('\n') if line.strip()]))
        
        requests.post(f"{SERVER_URL}/api/wifi/set_results", json={"networks": ssids}, timeout=5)
        update_ui("WIFI SCAN", f"FOUND {len(ssids)}")
        time.sleep(2)
    except Exception as e:
        print(f"WiFi Scan Error: {e}")
        update_ui("WIFI SCAN", "FAILED (No nmcli?)")
        time.sleep(2)

def connect_wifi(ssid, pw):
    update_ui("CONNECTING...", ssid[:15])
    try:
        subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', pw], timeout=15)
        update_ui("WIFI CONNECTED", ssid[:15])
        time.sleep(2)
    except Exception as e:
        print(f"WiFi Connect Error: {e}")
        update_ui("WIFI FAILED", "CHECK PW")
        time.sleep(2)

# --- BESTEHENDE DRUCK-LOGIK ---
def download_and_save_bmp(img_url_path):
    try:
        # Falls der Pfad schon mit 'images/' oder '/' beginnt, bereinigen wir das hier
        clean_path = img_url_path.lstrip('/')
        if not clean_path.startswith('images/') and not clean_path.startswith('data/'):
            # Manchmal liefert der Server nur den relativen Bildpfad
            full_url = f"{SERVER_URL}/images/{clean_path}"
        else:
            full_url = f"{SERVER_URL}/{clean_path}"

        r = requests.get(full_url, timeout=5)
        if r.status_code == 200:
            with Image.open(BytesIO(r.content)) as img:
                if img.width > 384:
                    ratio = 384 / float(img.width)
                    new_h = int(float(img.height) * float(ratio))
                    img = img.resize((384, new_h), Image.Resampling.LANCZOS)
                img_bw = img.convert("1")
                img_bw.save(TEMP_BMP_PATH, "BMP")
                return True
    except Exception as e:
        print(f"Fehler Bild: {e}")
    return False

def print_card(data):
    if not p or not data: return
    try:
        name = data.get('name', 'Unknown')
        update_ui("SUMMONING...", name[:15])
        
        p._raw(b'\x1b\x40') 
        time.sleep(0.1)
        
        p.set(align='left', font='a', width=2, height=2)
        p.text(f"{name}\n")
        
        p.set(align='left', font='a', width=1, height=1, bold=True)
        mana = data.get('mana_cost', '')
        p.text(f"Cost: {mana} (CMC: {current_cmc})\n")
        
        # Bild laden, falls aktiviert
        img_url = data.get('image', '')
        if img_url and download_and_save_bmp(img_url):
            time.sleep(0.3)
            p.set(align='center')
            p.image(TEMP_BMP_PATH) 
            time.sleep(0.3)
            
        p.set(align='left', font='a', bold=True)
        p.text(f"\n{data.get('type_line', '')}\n")
        p.text("-" * 32 + "\n")
        p.set(align='left', font='a', bold=False) 
        p.text(f"{data.get('oracle_text', '')}\n")
        
        if data.get('stats'):
            p.set(align='right', font='a', bold=True)
            p.text(f"[{data['stats']}]\n")
            
        p.text("\n\n\n\n")
        p.flush()
        
    except Exception as e:
        print(f"Druckfehler: {e}")
    finally:
        update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

# --- GPIO SETUP & MAIN LOOP ---
GPIO.setmode(GPIO.BOARD)
GPIO.setup([UP_PIN, PRINT_PIN, DOWN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)

update_ui("MOMIR READY", f"CMC: {current_cmc}")

LAST_POLL_TIME = 0
POLL_INTERVAL = 1.5  # Zeit in Sekunden zwischen den Abfragen

try:
    while True:
        current_time = time.time()

        # 1. WEB POLL (Zeitlich gebremst, damit Tasten nicht blockieren)
        if current_time - LAST_POLL_TIME > POLL_INTERVAL:
            LAST_POLL_TIME = current_time
            try:
                r = requests.get(f"{SERVER_URL}/api/pi_poll", params={"token": AUTH_TOKEN}, timeout=0.1)
                if r.status_code == 200:
                    cmd = r.json()
                    c_type = cmd.get("type")
                    if c_type == "print":
                        print_card(cmd.get("data"))
                    elif c_type == "scan":
                        scan_wifi()
                    elif c_type == "connect":
                        connect_wifi(cmd.get("ssid"), cmd.get("pw"))
            except: pass

        # 2. UP / DOWN Buttons
        if GPIO.input(UP_PIN) == GPIO.LOW:
            start = time.time()
            while GPIO.input(UP_PIN) == GPIO.LOW: time.sleep(0.05)
            if (time.time() - start) > HOLD_THRESHOLD:
                current_cat_idx = (current_cat_idx + 1) % len(CATEGORIES)
            else:
                current_cmc = min(16, current_cmc + 1)
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

        if GPIO.input(DOWN_PIN) == GPIO.LOW:
            start = time.time()
            while GPIO.input(DOWN_PIN) == GPIO.LOW: time.sleep(0.05)
            if (time.time() - start) > HOLD_THRESHOLD:
                current_cat_idx = (current_cat_idx - 1) % len(CATEGORIES)
            else:
                current_cmc = max(1, current_cmc - 1)
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

        # 3. PRINT BUTTON (Drucken ODER Toggle)
        if GPIO.input(PRINT_PIN) == GPIO.LOW:
            start = time.time()
            while GPIO.input(PRINT_PIN) == GPIO.LOW: 
                time.sleep(0.05)
            
            # --- FEATURE 1: LANGE GEDRÜCKT -> BILD TOGGLE ---
            if (time.time() - start) > HOLD_THRESHOLD:
                try:
                    r = requests.post(f"{SERVER_URL}/api/toggle_image", timeout=2)
                    if r.status_code == 200:
                        status = r.json().get("print_images")
                        update_ui("IMAGES:", "ON" if status else "OFF")
                except:
                    update_ui("TOGGLE", "FAILED")
                time.sleep(1)
                update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")
            
            # --- KURZ GEDRÜCKT -> LOKAL DRUCKEN ---
            else:
                try:
                    cat = CATEGORIES[current_cat_idx]
                    update_ui("FETCHING...", cat[:12].upper())
                    
                    # Routing exakt wie in der Server-API definiert
                    if cat == "lands":
                        url = f"{SERVER_URL}/api/random_land"
                    else:
                        url = f"{SERVER_URL}/api/random/{cat}/{current_cmc}"
                        
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        print_card(r.json())
                    else:
                        update_ui("SERVER ERROR", f"CODE: {r.status_code}")
                        time.sleep(1.5)
                except Exception as e:
                    print(f"Fehler beim Holen der Karte: {e}")
                    update_ui("CONN. ERROR", "CHECK SERVER")
                    time.sleep(1.5)
                    
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")
            
        time.sleep(0.05)
except KeyboardInterrupt:
    GPIO.cleanup()