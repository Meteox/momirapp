from flask import Flask, jsonify, request, send_from_directory, render_template
import os
import random
import json

app = Flask(__name__)

# --- CONFIG ---
AUTH_TOKEN = "zhmwsdl<3" 
PI_COMMAND_QUEUE = []

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
                # HIER IST DER FIX: Wir machen den Pfad relativ zum "www" Ordner!
                # Dadurch liefert er "data/..." statt "www/data/..." an den Pi.
                rel_path = os.path.relpath(os.path.join(root, file), WWW_DIR)
                file_list.append(rel_path.replace("\\", "/"))
    return jsonify(file_list)

# --- NEU: API FÜR DIE WARTESCHLANGE (QUEUE) ---

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
        return jsonify(json.load(f))

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
    results = []
    if not query: 
        return jsonify([])
    for root, dirs, files in os.walk(DATA_ROOT):
        for file in files:
            if file.endswith('.json'):
                if query in file.lower():
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        try:
                            card = json.load(f)
                            if query in card['name'].lower():
                                results.append(card)
                        except:
                            continue
            if len(results) >= 20: 
                break
    return jsonify(results)

@app.route('/api/enqueue', methods=['POST'])
def enqueue_print():
    card_data = request.json
    if card_data:
        PI_COMMAND_QUEUE.append({"type": "print", "data": card_data})
        return jsonify({"status": "Printed"}), 200
    return jsonify({"status": "No data"}), 400

# --- DATEI-DIENST (URL OHNE WWW) ---

@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory(DATA_ROOT, filename)

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(IMAGE_ROOT, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)