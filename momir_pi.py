import json
import random
import time
import os
import requests
import RPi.GPIO as GPIO
from escpos.printer import Serial
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas

# --- CONFIG ---
SERVER_URL = "http://85.215.219.243:5000"
PI_BASE_DIR = os.path.expanduser("~/momirapp/www") 
AUTH_TOKEN = "zhmwsdl<3"

UP_PIN, PRINT_PIN, DOWN_PIN = 11, 13, 15
CATEGORIES = ["creatures", "artifacts", "battles", "enchantments", "instants", "lands", "planeswalkers", "sorceries"]
current_cat_idx = 0
current_cmc = 1
HOLD_THRESHOLD = 0.6 

# 1. OLED Setup
try:
    serial_int = i2c(port=1, address=0x3C)
    device = ssd1306(serial_int, width=128, height=32)
    has_screen = True
except Exception as e:
    has_screen = False

def update_ui(line1, line2="", progress=None):
    if has_screen:
        try:
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white")
                draw.text((5, 4), line1, fill="white")
                if progress is not None:
                    bar_width = int((progress / 100) * 118)
                    draw.rectangle((5, 20, 5 + bar_width, 26), fill="white")
                else:
                    draw.text((5, 18), line2, fill="white")
        except: pass

def print_card(card_data):
    p = None
    try:
        # Versuch mit Standard-Baudrate 9600
        p = Serial(devfile='/dev/serial0', baudrate=9600, timeout=1.0)
        if not p or not card_data: return
        
        update_ui("DRUCKE...", card_data.get('name', '')[:12])
        
        # Nur absolute Standard-Befehle
        p._raw(b'\x1b\x40') # Reset
        time.sleep(0.2)
        
        # Name
        p.set(align='left', font='a', width=2, height=2)
        p.text(f"{card_data.get('name', 'Unknown')}\n")
        
        # Bild (Nur wenn Datei existiert)
        img_rel = card_data.get('image', '').lstrip('/')
        img_path = os.path.join(PI_BASE_DIR, img_rel)
        if os.path.exists(img_path):
            p.set(align='center')
            p.image(img_path)
            time.sleep(0.5)
            
        # Text
        p.set(align='left', font='a', bold=True, width=1, height=1)
        p.text(f"\n{card_data.get('type_line', '')}\n")
        p.text("-" * 32 + "\n")
        p.set(align='left', font='a', bold=False) 
        p.text(f"{card_data.get('oracle_text', '')}\n")
        
        if card_data.get('stats'):
            p.set(align='right', font='a', bold=True)
            p.text(f"\n[{card_data['stats']}]\n")
            
        p.text("\n\n\n") # Weniger Vorschub um Papier zu sparen
        
    except Exception as e:
        print(f"Fehler: {e}")
    finally:
        if p: p.close()
        update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

def perform_sync():
    update_ui("SYNC...", "START")
    try:
        r = requests.get(f"{SERVER_URL}/api/sync/manifest", timeout=10)
        if r.status_code == 200:
            for item in r.json():
                local = os.path.join(PI_BASE_DIR, item.lstrip('/'))
                if not os.path.exists(local):
                    os.makedirs(os.path.dirname(local), exist_ok=True)
                    res = requests.get(f"{SERVER_URL}/{item}")
                    with open(local, 'wb') as f: f.write(res.content)
        update_ui("SYNC OK")
        time.sleep(1)
    except: update_ui("SYNC ERROR")

def poll_server():
    try:
        r = requests.get(f"{SERVER_URL}/api/pi_poll", params={"token": AUTH_TOKEN}, timeout=0.2)
        if r.status_code == 200:
            cmd = r.json()
            if cmd.get("type") == "sync": perform_sync()
            elif cmd.get("type") == "print": print_card(cmd.get("data"))
    except: pass

# --- GPIO ---
GPIO.setmode(GPIO.BOARD)
GPIO.setup([UP_PIN, PRINT_PIN, DOWN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)

update_ui("MOMIR VIG", "BEREIT")

try:
    while True:
        poll_server()
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

        if GPIO.input(PRINT_PIN) == GPIO.LOW:
            # Karte lokal suchen
            path = os.path.join(PI_BASE_DIR, "data", CATEGORIES[current_cat_idx])
            if CATEGORIES[current_cat_idx] != "lands":
                path = os.path.join(path, str(current_cmc))
            
            if os.path.exists(path):
                files = [f for f in os.listdir(path) if f.endswith('.json')]
                if files:
                    with open(os.path.join(path, random.choice(files)), 'r') as f:
                        print_card(json.load(f))
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()