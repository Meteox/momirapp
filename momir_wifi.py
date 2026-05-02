import time
import requests
import subprocess

# --- CONFIG ---
SERVER_URL = "http://85.215.219.243:5000"
AUTH_TOKEN = "zhmwsdl<3"
POLL_INTERVAL = 1.0  # Prüft jede Sekunde nach WLAN-Befehlen

def scan_wifi():
    print("[WiFi] Starte Hardcore-Scan (Trennen -> Scannen -> Verbinden)...")
    current_ssid = ""
    try:
        # 1. Aktuelles Netzwerk merken
        out = subprocess.check_output(['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi']).decode('utf-8')
        for line in out.split('\n'):
            if line.startswith('ja:') or line.startswith('yes:'):
                current_ssid = line.split(':')[1].strip()
                break
                
        print(f"[WiFi] Aktuell verbunden mit: {current_ssid}")

        # 2. Verbindung hart trennen (Gibt die Antenne frei)
        print("[WiFi] Trenne Verbindung für den Scan...")
        subprocess.run(['sudo', 'nmcli', 'dev', 'disconnect', 'wlan0'], timeout=10)
        time.sleep(2)

        # 3. Scannen! (Chip ist jetzt frei und scannt alle Kanäle)
        print("[WiFi] Scanne Umgebung...")
        scan_output = subprocess.check_output(['sudo', 'iwlist', 'wlan0', 'scan'], stderr=subprocess.STDOUT).decode('utf-8')

        # 4. SOFORT wieder verbinden (Wir brauchen Internet für den Server!)
        if current_ssid:
            print(f"[WiFi] Verbinde wieder mit {current_ssid}...")
            subprocess.run(['sudo', 'nmcli', 'dev', 'wifi', 'connect', current_ssid], timeout=20)
            time.sleep(3) # Dem Pi kurz Zeit geben, die IP wiederherzustellen
        else:
            # Falls er vorher nicht verbunden war, versuchen wir wlan0 einfach wieder hochzufahren
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'])

        # 5. Ergebnisse auswerten
        ssids = []
        for line in scan_output.split('\n'):
            if 'ESSID:' in line:
                ssid = line.split('ESSID:"')[1].split('"')[0].strip()
                if ssid and ssid not in ssids and "\\x00" not in ssid:
                    ssids.append(ssid)

        # 6. An Server senden
        print(f"[WiFi] Scan beendet. Sende {len(ssids)} Netzwerke an den Server...")
        requests.post(f"{SERVER_URL}/api/wifi/set_results", json={"networks": ssids}, timeout=5)
        
    except Exception as e:
        print(f"[WiFi] Fehler beim Hardcore-Scan: {e}")
        # Notfall-Fallback: Versuchen, irgendwie wieder online zu kommen!
        if current_ssid:
            subprocess.run(['sudo', 'nmcli', 'dev', 'wifi', 'connect', current_ssid])

def connect_wifi(ssid, pw):
    print(f"[WiFi] Versuche NEUE Verbindung mit '{ssid}'...")
    try:
        if pw:
            subprocess.run(['sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid, 'password', pw], timeout=20, check=True)
        else:
            subprocess.run(['sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid], timeout=20, check=True)
            
        print(f"[WiFi] Erfolgreich mit '{ssid}' verbunden!")
    except Exception as e:
        print(f"[WiFi] Fehler beim Verbinden: {e}")

def main():
    print("[WiFi System] Gestartet und bereit für Befehle.")
    while True:
        try:
            r = requests.get(f"{SERVER_URL}/api/pi_poll", params={"token": AUTH_TOKEN}, timeout=0.5)
            if r.status_code == 200:
                cmd = r.json()
                c_type = cmd.get("type")
                
                if c_type == "scan":
                    scan_wifi()
                elif c_type == "connect":
                    connect_wifi(cmd.get("ssid"), cmd.get("pw"))
                    
        except requests.exceptions.RequestException:
            pass
        except Exception as e:
            print(f"[WiFi System] Fehler in Hauptschleife: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()