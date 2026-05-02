import os
import json
import hashlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, "www", "data", "tokens")
IGNORE_LIST_PATH = os.path.join(BASE_DIR, "ignored_tokens.json")

def get_file_hash(data):
    fingerprint = f"{data.get('name')}|{data.get('stats')}|{data.get('oracle_text')}"
    return hashlib.md5(fingerprint.encode('utf-8')).hexdigest()

def cleanup_tokens():
    if not os.path.exists(TOKEN_PATH): return

    seen_variants = {}
    ignored_ids = [] # Hier speichern wir die IDs der gelöschten Duplikate

    files = [f for f in os.listdir(TOKEN_PATH) if f.endswith('.json')]
    
    for filename in files:
        file_path = os.path.join(TOKEN_PATH, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                card_data = json.load(f)
            
            v_hash = get_file_hash(card_data)
            # Extrahiere ID aus Filename (Name_ID.json)
            current_id = filename.split('_')[-1].replace('.json', '')

            if v_hash in seen_variants:
                # Duplikat -> ID merken und löschen
                ignored_ids.append(current_id)
                
                img_rel_path = card_data.get('image', '').lstrip('/')
                img_full_path = os.path.join(BASE_DIR, "www", img_rel_path)
                if os.path.exists(img_full_path): os.remove(img_full_path)
                os.remove(file_path)
            else:
                seen_variants[v_hash] = filename
        except: continue

    # Liste speichern für den Scraper
    with open(IGNORE_LIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(ignored_ids, f)
    
    print(f"Bereinigt. {len(ignored_ids)} IDs auf Ignorier-Liste gesetzt.")

if __name__ == "__main__":
    cleanup_tokens()