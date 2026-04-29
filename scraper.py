import os
import json
import requests
import re
import time
from tqdm import tqdm
from PIL import Image
from io import BytesIO

# --- KONFIGURATION ---
BASE_PATH = r"C:\MomirServer\www\data"
IMG_PATH = r"C:\MomirServer\www\images"
BULK_DATA_URL = "https://api.scryfall.com/bulk-data"

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
        time.sleep(0.18) 
        headers = {'User-Agent': 'MomirPrinterMaster/1.0'}
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
    print("Starte Scryfall Update v6.3 (Lands & Spells)...")
    resp = requests.get(BULK_DATA_URL).json()
    url = next(d['download_uri'] for d in resp['data'] if d['type'] == 'default_cards')
    all_cards = requests.get(url).json()
    
    os.makedirs(IMG_PATH, exist_ok=True)

    for card in tqdm(all_cards, desc="Sortiere"):
        try:
            if card.get('digital'): continue
            
            type_line = card.get('type_line', '')
            name = sanitize_filename(card.get('name'))
            layout = card.get('layout', '')
            set_code = card.get('set', '').lower()
            
            # --- PRIORITÄTEN-LOGIK ---
            is_token = (layout in ['token', 'double_faced_token'] or "Token" in type_line)
            is_land = "Land" in type_line
            is_basic = "Basic" in type_line

            if is_token:
                target_folder = "tokens"
                dest_dir = os.path.join(BASE_PATH, target_folder)
            elif is_land:
                if is_basic: continue # Keine Standardländer
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
                else: continue
                
                dest_dir = os.path.join(BASE_PATH, target_folder, str(cmc))

            os.makedirs(dest_dir, exist_ok=True)
            json_file = os.path.join(dest_dir, f"{name}.json")
            img_file = os.path.join(IMG_PATH, f"{name}.png")

            if not os.path.exists(json_file):
                card_data = {
                    'name': card.get('name'),
                    'mana_cost': card.get('mana_cost', ''),
                    'type_line': type_line,
                    'oracle_text': get_card_text(card),
                    'stats': f"{card.get('power', '?')}/{card.get('toughness', '?')}" if ('Creature' in type_line or is_token) else "",
                    'image': f"/images/{name}.png"
                }
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(card_data, f, ensure_ascii=False, indent=2)

            if not os.path.exists(img_file):
                img_uris = card.get('image_uris')
                if not img_uris and 'card_faces' in card:
                    img_uris = card['card_faces'][0].get('image_uris')
                if img_uris and 'art_crop' in img_uris:
                    process_image(img_uris['art_crop'], img_file)
                        
        except Exception:
            continue

if __name__ == "__main__":
    sort_cards()