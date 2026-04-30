import json
import requests
import time
import os
import RPi.GPIO as GPIO
from escpos.printer import Serial
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import Image

# --- CONFIG ---
UP_PIN, PRINT_PIN, DOWN_PIN = 11, 13, 15
SERVER_URL = "http://192.168.178.55:5000" # DEINE SERVER-IP EINTRAGEN
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_IMG = os.path.join(BASE_DIR, "temp_print.png")

# 1. OLED Setup
try:
    serial_int = i2c(port=1, address=0x3C)
    device = ssd1306(serial_int, width=128, height=32)
    has_screen = True
except:
    has_screen = False

def update_ui(line1, line2="", progress=None):
    if has_screen:
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white")
            draw.text((5, 4), line1, fill="white")
            if progress is not None:
                bar_width = int((progress / 100) * 118)
                draw.rectangle((5, 20, 5 + bar_width, 26), fill="white")
            else:
                draw.text((5, 18), line2, fill="white")

# 2. Printer Setup (DEIN STABILER SETUP)
try:
    p = Serial(devfile='/dev/serial0', baudrate=9600, timeout=1.0)
except:
    p = None

current_cmc = 1

def print_card(cmc):
    update_ui("SUMMONING...", "WAITING FOR SERVER")
    try:
        # Hole Karte vom Server
        resp = requests.get(f"{SERVER_URL}/get_card/{cmc}", timeout=5)
        if resp.status_code != 200: return
        card = resp.json()
        
        name = card.get('name', 'Unknown')
        update_ui("SUMMONING...", name[:15])

        # Bild herunterladen
        img_url = f"{SERVER_URL}{card.get('image')}"
        img_resp = requests.get(img_url, timeout=5)
        if img_resp.status_code == 200:
            with open(TEMP_IMG, 'wb') as f:
                f.write(img_resp.content)

        if p:
            # DEIN STABILER RESET & PRINT FLOW
            p._raw(b'\x1b\x40') # Reset
            time.sleep(0.1)
            
            # Header
            p.set(align='left', font='a', width=2, height=2)
            p.text(f"{name}\n")
            p.set(align='left', font='a', width=1, height=1, bold=True)
            p.text(f"Cost: {card.get('mana_cost', '0')} (CMC: {cmc})\n")
            
            # Bild drucken
            if os.path.exists(TEMP_IMG):
                p.set(align='center')
                p.image(TEMP_IMG) # escpos kümmert sich um die Konvertierung
                time.sleep(0.3)
            
            # Rules & Stats
            p.set(align='left', font='a', bold=True)
            p.text(f"\n{card.get('type_line', '')}\n")
            p.text("-" * 32 + "\n")
            p.set(align='left', font='a', bold=False) 
            p.text(f"{card.get('oracle_text', '')}\n")
            
            if card.get('stats'):
                p.set(align='right', font='a', bold=True)
                p.text(f"[{card['stats']}]\n")
            
            p.text("\n\n\n\n")
            p.flush()
            
    except Exception as e:
        update_ui("ERROR", str(e)[:15])
        print(f"Error: {e}")

# GPIO Setup & Loop wie gehabt...
GPIO.setmode(GPIO.BOARD)
GPIO.setup([UP_PIN, PRINT_PIN, DOWN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)

update_ui("MOMIR VIG", f"CMC: {current_cmc}")

try:
    while True:
        if GPIO.input(UP_PIN) == GPIO.LOW:
            current_cmc = min(16, current_cmc + 1)
            update_ui("SELECT CMC", f"CMC: {current_cmc}")
            time.sleep(0.3)
        
        if GPIO.input(DOWN_PIN) == GPIO.LOW:
            current_cmc = max(1, current_cmc - 1)
            update_ui("SELECT CMC", f"CMC: {current_cmc}")
            time.sleep(0.3)

        if GPIO.input(PRINT_PIN) == GPIO.LOW:
            print_card(current_cmc)
            update_ui("MOMIR VIG", f"CMC: {current_cmc}")
            
        time.sleep(0.05)
except KeyboardInterrupt:
    GPIO.cleanup()
