import os
import json
import requests
import re
import time
from tqdm import tqdm
from PIL import Image
from io import BytesIO

# --- KONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(BASE_DIR, "www", "data")
IMG_PATH = os.path.join(BASE_DIR, "www", "images")
BULK_DATA_URL = "https://api.scryfall.com/bulk-data"
IGNORE_LIST_PATH = os.path.join(BASE_DIR, "ignored_tokens.json")
IGNORED_IDS = []
if os.path.exists(IGNORE_LIST_PATH):
    with open(IGNORE_LIST_PATH, 'r', encoding='utf-8') as f:
        IGNORED_IDS = json.load(f)

UN_SETS = ['ugl', 'unh', 'ust', 'unp', 'unf', 'und', 'unq', 'hho', 'cmb1', 'cmb2']

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def get_card_text(card):
    if 'card_faces' in card:
        parts = []
        for face in card['card_faces']:
            face_text = face.get('oracle_text', '').strip()
            if face_text:
                parts.append(f"[{face.get('name')}]\n{face_text}")
        full_text = "\n\n---\n\n".join(parts)
        return full_text if full_text else "Vanilla (No Text)"
    text = card.get('oracle_text', '').strip()
    return text if text else "Vanilla (No Text)"

def process_image(url, save_path):
    try:
        time.sleep(0.15) 
        headers = {'User-Agent': 'MomirPrinterMaster/1.1'}
        response = requests.get(url, timeout=15, headers=headers)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            img = img.convert('L')
            w_percent = (384 / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((384, h_size), Image.Resampling.LANCZOS)
            img.save(save_path, "PNG")
            return True
    except Exception:
        return False

def sort_cards():
    print("Starte Scryfall Update v6.6 (Stable ID Naming)...")
    resp = requests.get(BULK_DATA_URL).json()
    url = next(d['download_uri'] for d in resp['data'] if d['type'] == 'default_cards')
    all_cards = requests.get(url).json()
    
    os.makedirs(IMG_PATH, exist_ok=True)

    for card in tqdm(all_cards, desc="Verarbeite Karten"):
        try:
            # --- IGNORE LIST CHECK ---
            scryfall_id = card.get('id', '')
            if scryfall_id in IGNORED_IDS or scryfall_id[:8] in IGNORED_IDS:
                continue

            if card.get('digital'): continue
            
            type_line = card.get('type_line', '')
            layout = card.get('layout', '')
            set_code = card.get('set', '').lower()
            
            # --- PRIORITÄTEN-LOGIK ---
            is_token = (layout in ['token', 'double_faced_token'] or "Token" in type_line)
            is_land = "Land" in type_line
            is_basic = "Basic" in type_line

            target_folder = None
            dest_dir = None

            if is_token:
                target_folder = "tokens"
                dest_dir = os.path.join(BASE_PATH, target_folder)
            elif is_land:
                if is_basic: continue 
                target_folder = "lands"
                dest_dir = os.path.join(BASE_PATH, target_folder)
            else:
                cmc = int(card.get('cmc', 0))
                is_unset = (set_code in UN_SETS or card.get('border_color') == 'silver' or card.get('security_stamp') == 'acorn')
                
                if is_unset: target_folder = "unset"
                elif "Creature" in type_line: target_folder = "creatures"
                elif "Instant" in type_line: target_folder = "instants"
                elif "Sorcery" in type_line: target_folder = "sorceries"
                elif "Battle" in type_line: target_folder = "battles"
                elif "Planeswalker" in type_line: target_folder = "planeswalkers"
                elif "Artifact" in type_line: target_folder = "artifacts"
                elif "Enchantment" in type_line: target_folder = "enchantments"
                
                if target_folder:
                    dest_dir = os.path.join(BASE_PATH, target_folder, str(cmc))

            # Falls kein Zielordner gefunden wurde (z.B. Card-Backs o.ä.), überspringen
            if not dest_dir:
                continue

            # --- DATEINAMEN LOGIK ---
            clean_name = sanitize_filename(card.get('name'))
            
            # NUR Tokens bekommen die ID, um Re-Downloads der Haupt-DB zu vermeiden
            if is_token:
                scryfall_id_short = card.get('id', '')[:8]
                file_identifier = f"{clean_name}_{scryfall_id_short}"
            else:
                file_identifier = clean_name
            
            os.makedirs(dest_dir, exist_ok=True)
            json_file = os.path.join(dest_dir, f"{file_identifier}.json")
            img_file = os.path.join(IMG_PATH, f"{file_identifier}.png")

            # --- STATS LOGIK ---
            stats = ""
            if 'power' in card and 'toughness' in card:
                stats = f"{card.get('power')}/{card.get('toughness')}"
            elif 'loyalty' in card:
                stats = f"Loyalty: {card.get('loyalty')}"
            elif 'defense' in card:
                stats = f"Defense: {card.get('defense')}"

            should_write_json = False
            if not os.path.exists(json_file):
                should_write_json = True
            else:
                # Prüfen, ob Stats in existierender Datei fehlen
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if not existing_data.get('stats') and stats:
                            should_write_json = True
                except:
                    should_write_json = True

            if should_write_json:
                card_data = {
                    'name': card.get('name'),
                    'mana_cost': card.get('mana_cost', ''),
                    'type_line': type_line,
                    'oracle_text': get_card_text(card),
                    'stats': stats,
                    'image': f"/images/{file_identifier}.png"
                }
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(card_data, f, ensure_ascii=False, indent=2)

            # Bild verarbeiten falls es fehlt
            if not os.path.exists(img_file):
                img_uris = card.get('image_uris')
                if not img_uris and 'card_faces' in card:
                    img_uris = card['card_faces'][0].get('image_uris')
                if img_uris and 'art_crop' in img_uris:
                    process_image(img_uris['art_crop'], img_file)
                        
        except Exception as e:
            # Im Fehlerfall nicht abstürzen, sondern Karte überspringen
            continue

if __name__ == "__main__":
    sort_cards()