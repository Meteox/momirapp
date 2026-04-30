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
from PIL import Image # Wichtig für die BMP-Simulation

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

def print_card(data):
    if not p or not data: return
    try:
        name = data.get('name', 'Unknown')
        update_ui("SUMMONING...", name[:15])
        
        # RESET
        p._raw(b'\x1b\x40') 
        time.sleep(0.1)
        
        # Name
        p.set(align='left', font='a', width=2, height=2)
        p.text(f"{name}\n")
        
        # BILD-LOGIK (Simuliert deine alten BMPs)
        img_rel = data.get('image', '').lstrip('/')
        img_path = os.path.join(PI_BASE_DIR, img_rel)
        
        if os.path.exists(img_path):
            # Wir öffnen das PNG und konvertieren es in 1-Bit (Schwarz/Weiß)
            # Das ist genau das, was deine alten BMPs waren.
            with Image.open(img_path) as img:
                img_bw = img.convert("1") # "1" steht für 1-Bit Pixel (Dithering)
                time.sleep(0.2)
                p.set(align='center')
                p.image(img_bw) # Der Drucker bekommt jetzt "fertige" Daten
                time.sleep(0.5)
            
        # Details
        p.set(align='left', font='a', bold=True)
        p.text(f"\n{data.get('type_line', '')}\n")
        p.text("-" * 32 + "\n")
        p.set(align='left', font='a', bold=False) 
        p.text(f"{data.get('oracle_text', '')}\n")
        
        if data.get('stats'):
            p.set(align='right', font='a', bold=True)
            p.text(f"[{data['stats']}]\n")
            
        p.text("\n\n\n\n")
        
    except Exception as e:
        print(f"Print error: {e}")

# --- RESTLICHER CODE (GPIO & LOOP) BLEIBT GLEICH ---
GPIO.setmode(GPIO.BOARD)
GPIO.setup([UP_PIN, PRINT_PIN, DOWN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)

update_ui("MOMIR READY", "V3.2")

try:
    while True:
        try:
            r = requests.get(f"{SERVER_URL}/api/pi_poll", params={"token": AUTH_TOKEN}, timeout=0.1)
            if r.status_code == 200:
                cmd = r.json()
                if cmd.get("type") == "print": print_card(cmd.get("data"))
        except: pass

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
            cat = CATEGORIES[current_cat_idx]
            path = os.path.join(PI_BASE_DIR, "data", cat)
            if cat != "lands": path = os.path.join(path, str(current_cmc))
            if os.path.exists(path):
                files = [f for f in os.listdir(path) if f.endswith('.json')]
                if files:
                    with open(os.path.join(path, random.choice(files)), 'r') as f:
                        print_card(json.load(f))
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")
        time.sleep(0.05)
except KeyboardInterrupt:
    GPIO.cleanup()
