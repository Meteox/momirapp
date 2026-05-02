import time
import requests
import subprocess

# --- CONFIG ---
SERVER_URL = "http://85.215.219.243:5000"
AUTH_TOKEN = "zhmwsdl<3"
POLL_INTERVAL = 1.0  # Prüft jede Sekunde nach WLAN-Befehlen vom Server

def scan_wifi():
    print("[WiFi] Starte aktiven Umgebungsscan...")
    try:
        # 1. Wir zwingen das Interface zu einem echten Rescan im Hintergrund
        subprocess.run(['nmcli', 'device', 'wifi', 'rescan'], timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Dem Pi kurz Zeit geben, die neu gefundenen Netzwerke zu verarbeiten
        time.sleep(2)

        # 2. Wir holen alle aktuell sichtbaren SSIDs
        result = subprocess.check_output(
            ['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi', 'list'],
            stderr=subprocess.STDOUT
        )
        
        # 3. Bereinigen: Keine Duplikate, keine leeren Namen
        ssids = []
        for line in result.decode('utf-8').split('\n'):
            line = line.strip()
            # Wenn die Zeile nicht leer ist und noch nicht in der Liste steht
            if line and line not in ssids:
                ssids.append(line)
        
        # Sende die Liste an den Server
        print(f"[WiFi] Scan beendet. Sende {len(ssids)} Netzwerke an den Server...")
        requests.post(f"{SERVER_URL}/api/wifi/set_results", json={"networks": ssids}, timeout=3)
        
    except Exception as e:
        print(f"[WiFi] Fehler beim Scannen: {e}")

def connect_wifi(ssid, pw):
    print(f"[WiFi] Versuche Verbindung mit '{ssid}'...")
    try:
        # Verbindet sich mit dem neuen Netzwerk
        if pw:
            subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', pw], timeout=15, check=True)
        else:
            subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid], timeout=15, check=True)
            
        print(f"[WiFi] Erfolgreich mit '{ssid}' verbunden!")
    except Exception as e:
        print(f"[WiFi] Fehler beim Verbinden: {e}")

def main():
    print("[WiFi System] Gestartet und bereit für Befehle.")
    while True:
        try:
            # Pollt den Server nach WLAN-Befehlen
            r = requests.get(f"{SERVER_URL}/api/pi_poll", params={"token": AUTH_TOKEN}, timeout=0.5)
            if r.status_code == 200:
                cmd = r.json()
                c_type = cmd.get("type")
                
                if c_type == "scan":
                    scan_wifi()
                elif c_type == "connect":
                    connect_wifi(cmd.get("ssid"), cmd.get("pw"))
                    
        except requests.exceptions.RequestException:
            # Server kurz nicht erreichbar -> Ignorieren und weitermachen
            pass
        except Exception as e:
            print(f"[WiFi System] Fehler in Hauptschleife: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()