import os
import json
from flask import Flask, render_template, request, jsonify
from scraper import get_random_card

app = Flask(__name__)

# --- NEUE GLOBALE VARIABLEN ---
AUTH_TOKEN = "zhmwsdl<3"
PRINT_IMAGES = True       # Status für den Bild-Druck
PI_COMMAND = None         # Briefkasten für Befehle an den Pi (z.B. "scan", "connect")
WIFI_NETWORKS = []        # Speichert die gefundenen WLANs vom Pi

# --- BESTEHENDE ROUTEN ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_card/<int:cmc>')
def get_card(cmc):
    card_type = request.args.get('type', 'creatures')
    card = get_random_card(cmc, card_type)
    
    if card:
        # FEATURE 1: Wenn Bild-Druck AUS ist, schicken wir einfach kein Bild an den Pi!
        global PRINT_IMAGES
        if not PRINT_IMAGES:
            card['image'] = '' 
        return jsonify(card)
    return jsonify({"error": "No card found"}), 404

# --- NEUE ROUTEN: BILD TOGGLE ---
@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({"print_images": PRINT_IMAGES})

@app.route('/api/toggle_image', methods=['POST'])
def toggle_image():
    global PRINT_IMAGES
    PRINT_IMAGES = not PRINT_IMAGES
    return jsonify({"status": "success", "print_images": PRINT_IMAGES})

# --- NEUE ROUTEN: WLAN MANAGEMENT ---
@app.route('/api/wifi/trigger_scan', methods=['POST'])
def trigger_scan():
    global PI_COMMAND, WIFI_NETWORKS
    WIFI_NETWORKS = [] # Alte Liste leeren
    PI_COMMAND = {"type": "scan"} # Befehl in den Briefkasten legen
    return jsonify({"status": "scan_triggered"})

@app.route('/api/wifi/set_results', methods=['POST'])
def set_wifi_results():
    global WIFI_NETWORKS
    data = request.json
    if data and 'networks' in data:
        WIFI_NETWORKS = data['networks']
    return jsonify({"status": "ok"})

@app.route('/api/wifi/get_results', methods=['GET'])
def get_wifi_results():
    return jsonify({"networks": WIFI_NETWORKS})

@app.route('/api/wifi/connect', methods=['POST'])
def wifi_connect():
    global PI_COMMAND
    data = request.json
    # Befehl in den Briefkasten legen
    PI_COMMAND = {
        "type": "connect",
        "ssid": data.get("ssid"),
        "pw": data.get("password")
    }
    return jsonify({"status": "connect_triggered"})

# --- PI POLLING ROUTE ---
@app.route('/api/pi_poll')
def pi_poll():
    global PI_COMMAND
    token = request.args.get('token')
    if token != AUTH_TOKEN: 
        return jsonify({"error": "unauthorized"}), 401
    
    # Wenn ein Befehl (Drucken, WLAN) im Briefkasten liegt, gib ihn dem Pi und leere ihn
    if PI_COMMAND:
        cmd = PI_COMMAND
        PI_COMMAND = None
        return jsonify(cmd)
        
    return jsonify({"type": "ping"})

if __name__ == '__main__':
    # Lauscht auf allen IPs im Netzwerk
    app.run(host='0.0.0.0', port=5000)