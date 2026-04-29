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
    print(f"OLED Setup Error: {e}")
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
        except:
            pass

# --- SYNC LOGIK ---
def perform_sync():
    update_ui("SYNCING...", "STARTING...")
    try:
        r = requests.get(f"{SERVER_URL}/api/sync/manifest", timeout=10)
        remote_files = r.json()
        total = len(remote_files)
        for i, rel_path in enumerate(remote_files):
            local_path = os.path.join(PI_BASE_DIR, rel_path)
            if not os.path.exists(local_path):
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                data = requests.get(f"{SERVER_URL}/{rel_path}").json()
                with open(local_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                
                img_rel = data['image'].lstrip('/')
                img_local = os.path.join(PI_BASE_DIR, img_rel)
                if not os.path.exists(img_local):
                    os.makedirs(os.path.dirname(img_local), exist_ok=True)
                    img_r = requests.get(f"{SERVER_URL}/{img_rel}")
                    with open(img_local, 'wb') as f:
                        f.write(img_r.content)
            
            if i % 20 == 0:
                update_ui("SYNCING...", f"{i}/{total}", progress=(i/total)*100)
        
        update_ui("SYNC COMPLETE", "READY")
        time.sleep(2)
    except Exception as e:
        update_ui("SYNC ERROR", str(e)[:15])
        time.sleep(2)

# --- PRINTER SETUP ---
def print_card(card_data):
    p = None
    try:
        # Wir nutzen Serial direkt. QR204 ist oft stabil auf /dev/serial0
        p = Serial(devfile='/dev/serial0', baudrate=9600, timeout=1.0)
        if not p or not card_data: return
        
        name = card_data.get('name', 'Unknown')
        update_ui("PRINTING...", name[:15])
        
        # Reset & Init
        p._raw(b'\x1b\x40') 
        time.sleep(0.1)
        
        # Name
        p.set(align='left', font='a', width=2, height=2)
        p.text(f"{name}\n")
        
        # Bild
        img_rel = card_data['image'].lstrip('/')
        img_path = os.path.join(PI_BASE_DIR, img_rel)
        if os.path.exists(img_path):
            p.set(align='center')
            p.image(img_path)
            # Nach dem Bild dem Drucker Zeit zum "Atmen" geben (Puffer leeren)
            time.sleep(0.5) 
            
        # Details
        p.set(align='left', font='a', bold=True, width=1, height=1)
        p.text(f"\n{card_data.get('type_line', '')}\n")
        p.text("-" * 32 + "\n")
        
        p.set(align='left', font='a', bold=False) 
        p.text(f"{card_data.get('oracle_text', '')}\n")
        
        if card_data.get('stats'):
            p.set(align='right', font='a', bold=True)
            p.text(f"\n[{card_data['stats']}]\n")
            
        p.text("\n\n\n\n")
        
    except Exception as e:
        print(f"Print error: {e}")
    finally:
        if p:
            p.close()
        update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

def get_local_random(category, cmc=None):
    if category == "lands":
        path = os.path.join(PI_BASE_DIR, "data", category)
    else:
        path = os.path.join(PI_BASE_DIR, "data", category, str(cmc))
    
    if os.path.exists(path):
        files = [f for f in os.listdir(path) if f.endswith('.json')]
        if files:
            with open(os.path.join(path, random.choice(files)), 'r', encoding='utf-8') as f:
                return json.load(f)
    return None

# --- GPIO SETUP ---
GPIO.setmode(GPIO.BOARD)
GPIO.setup([UP_PIN, PRINT_PIN, DOWN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)

update_ui("MOMIR VIG 3.1", "READY")

try:
    while True:
        # 1. POLL SERVER
        try:
            r = requests.get(f"{SERVER_URL}/api/pi_poll", params={"token": AUTH_TOKEN}, timeout=0.1)
            if r.status_code == 200:
                cmd = r.json()
                if cmd.get("type") == "sync": perform_sync()
                elif cmd.get("type") == "print": print_card(cmd.get("data"))
        except: pass

        # 2. UP BUTTON
        if GPIO.input(UP_PIN) == GPIO.LOW:
            start = time.time()
            while GPIO.input(UP_PIN) == GPIO.LOW: time.sleep(0.05)
            if (time.time() - start) > HOLD_THRESHOLD:
                current_cat_idx = (current_cat_idx + 1) % len(CATEGORIES)
            else:
                current_cmc = min(16, current_cmc + 1)
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

        # 3. DOWN BUTTON
        if GPIO.input(DOWN_PIN) == GPIO.LOW:
            start = time.time()
            while GPIO.input(DOWN_PIN) == GPIO.LOW: time.sleep(0.05)
            if (time.time() - start) > HOLD_THRESHOLD:
                current_cat_idx = (current_cat_idx - 1) % len(CATEGORIES)
            else:
                current_cmc = max(1, current_cmc - 1)
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

        # 4. PRINT
        if GPIO.input(PRINT_PIN) == GPIO.LOW:
            cat = CATEGORIES[current_cat_idx]
            card = get_local_random(cat, current_cmc if cat != "lands" else None)
            if card: 
                print_card(card)
            update_ui(CATEGORIES[current_cat_idx].upper(), f"CMC: {current_cmc}")

        time.sleep(0.05)
except KeyboardInterrupt:
    GPIO.cleanup()