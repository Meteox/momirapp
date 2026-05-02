from flask import Flask, jsonify, request, send_from_directory, render_template
import os
import random
import json

app = Flask(__name__)

# --- CONFIG & GLOBALE VARIABLEN ---
AUTH_TOKEN = "zhmwsdl<3" 
PI_COMMAND_QUEUE = []      # Für Druckaufträge und Sync
PRINT_IMAGES = True        # Status für den Bild-Druck
PI_COMMAND = None          # Briefkasten für WLAN-Befehle
WIFI_NETWORKS = []         # Speichert die gefundenen WLANs vom Pi

# Pfade
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WWW_DIR = os.path.join(BASE_DIR, "www")
DATA_ROOT = os.path.join(WWW_DIR, "data")
IMAGE_ROOT = os.path.join(WWW_DIR, "images")

# --- API FÜR DEN PI (POLLING & SYNC) ---

@app.route('/api/pi_poll')
def pi_poll():
    token = request.args.get("token")
    if token != AUTH_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
    
    # 1. Prüfe auf WLAN-Befehle (Priorität)
    global PI_COMMAND
    if PI_COMMAND:
        cmd = PI_COMMAND
        PI_COMMAND = None
        return jsonify(cmd)
        
    # 2. Prüfe auf Druck- oder Sync-Aufträge
    if PI_COMMAND_QUEUE:
        return jsonify(PI_COMMAND_QUEUE.pop(0))
        
    return jsonify({"type": "idle"}), 200

@app.route('/api/trigger_sync', methods=['POST'])
def trigger_sync():
    data = request.json
    if data and data.get("token") == AUTH_TOKEN:
        PI_COMMAND_QUEUE.clear()
        PI_COMMAND_QUEUE.append({"type": "sync"})
        return jsonify({"status": "Sync queued"}), 200
    return jsonify({"status": "Wrong token"}), 403

@app.route('/api/sync/manifest')
def get_manifest():
    file_list = []
    if not os.path.exists(DATA_ROOT):
        return jsonify({"error": f"Data folder not found in {DATA_ROOT}"}), 500
    for root, dirs, files in os.walk(DATA_ROOT):
        for file in files:
            if file.endswith(".json"):
                rel_path = os.path.relpath(os.path.join(root, file), WWW_DIR)
                file_list.append(rel_path.replace("\\", "/"))
    return jsonify(file_list)

# --- API FÜR DIE WARTESCHLANGE (QUEUE) ---

@app.route('/api/queue')
def get_queue():
    queue_summary = []
    for cmd in PI_COMMAND_QUEUE:
        if cmd['type'] == 'print':
            name = cmd['data'].get('name', 'Unbekannte Karte')
            queue_summary.append({"type": "print", "name": name})
        else:
            queue_summary.append({"type": cmd['type']})
    return jsonify(queue_summary)

@app.route('/api/queue/clear', methods=['POST'])
def clear_queue():
    data = request.json
    if data and data.get("token") == AUTH_TOKEN:
        PI_COMMAND_QUEUE.clear()
        return jsonify({"status": "Queue cleared"}), 200
    return jsonify({"status": "Wrong token"}), 403

# --- NEU: BILD TOGGLE ROUTEN ---

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({"print_images": PRINT_IMAGES})

@app.route('/api/toggle_image', methods=['POST'])
def toggle_image():
    global PRINT_IMAGES
    PRINT_IMAGES = not PRINT_IMAGES
    return jsonify({"status": "success", "print_images": PRINT_IMAGES})

# --- NEU: WLAN MANAGEMENT ROUTEN ---

@app.route('/api/wifi/trigger_scan', methods=['POST'])
def trigger_scan():
    global PI_COMMAND, WIFI_NETWORKS
    WIFI_NETWORKS = [] 
    PI_COMMAND = {"type": "scan"} 
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
    PI_COMMAND = {
        "type": "connect",
        "ssid": data.get("ssid"),
        "pw": data.get("password")
    }
    return jsonify({"status": "connect_triggered"})

# --- API FÜR DAS WEB-INTERFACE (STATS & SEARCH) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    stats = {}
    if not os.path.exists(DATA_ROOT):
        return jsonify({"FEHLER": f"Ordner nicht gefunden: {DATA_ROOT}"})
        
    categories = os.listdir(DATA_ROOT)
    if not categories:
        return jsonify({"FEHLER": "Der 'data' Ordner im 'www' Verzeichnis ist leer"})
        
    for cat in categories:
        cat_path = os.path.join(DATA_ROOT, cat)
        if os.path.isdir(cat_path):
            count = 0
            for r, d, files in os.walk(cat_path):
                count += len([f for f in files if f.endswith('.json')])
            if count > 0:
                stats[cat] = count
                
    if not stats:
        return jsonify({"FEHLER": "Keine .json Dateien in den Kategorien gefunden"})
        
    return jsonify(stats)

@app.route('/api/cmcs/<category>')
def get_cmcs(category):
    cat_path = os.path.join(DATA_ROOT, category)
    if not os.path.exists(cat_path): 
        return jsonify([])
    cmcs = sorted([d for d in os.listdir(cat_path) if os.path.isdir(os.path.join(cat_path, d)) and d.isdigit()], key=int)
    return jsonify(cmcs)

@app.route('/api/random/<category>/<cmc>')
def get_random_card(category, cmc):
    path = os.path.join(DATA_ROOT, category, str(cmc))
    if not os.path.exists(path):
        return jsonify({"error": "Path not found"}), 404
    files = [f for f in os.listdir(path) if f.endswith('.json')]
    if not files: 
        return jsonify({"error": "No files"}), 404
    with open(os.path.join(path, random.choice(files)), 'r', encoding='utf-8') as f:
        card = json.load(f)
        
        # FEATURE: Bild-Feld leeren, falls Bild-Druck ausgeschaltet ist
        global PRINT_IMAGES
        if not PRINT_IMAGES and 'image' in card:
            card['image'] = ''
            
        return jsonify(card)

@app.route('/api/random_land')
def get_random_land():
    path = os.path.join(DATA_ROOT, "lands")
    if not os.path.exists(path):
        return jsonify({"error": "Lands folder not found"}), 404
    files = [f for f in os.listdir(path) if f.endswith('.json')]
    if not files: 
        return jsonify({"error": "No lands found"}), 404
    with open(os.path.join(path, random.choice(files)), 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))

@app.route('/api/search')
def search_cards():
    query = request.args.get('q', '').lower()
    cat_filter = request.args.get('cat', 'global_search')
    results = []
    
    if not query: 
        return jsonify([])

    for root, dirs, files in os.walk(DATA_ROOT):
        if cat_filter == 'tokens' and 'tokens' not in root:
            continue
        if cat_filter == 'unset' and 'unset' not in root:
            continue
        if cat_filter not in ['global_search', 'tokens', 'unset'] and cat_filter not in root:
            continue

        for file in files:
            if file.endswith('.json'):
                if query in file.lower():
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            card = json.load(f)
                            if query in card.get('name', '').lower():
                                results.append(card)
                    except:
                        continue
            if len(results) >= 25: 
                break
        if len(results) >= 25: 
            break
    return jsonify(results)

@app.route('/api/enqueue', methods=['POST'])
def enqueue_print():
    card_data = request.json
    if card_data:
        # Falls der Bilddruck deaktiviert ist, das Bild vor dem Queueing entfernen
        global PRINT_IMAGES
        if not PRINT_IMAGES and 'image' in card_data:
            card_data['image'] = ''
            
        PI_COMMAND_QUEUE.append({"type": "print", "data": card_data})
        return jsonify({"status": "Printed"}), 200
    return jsonify({"status": "No data"}), 400

# --- DATEI-DIENST ---

@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory(DATA_ROOT, filename)

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(IMAGE_ROOT, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)