import time
import requests
import subprocess

# --- CONFIG ---
SERVER_URL = "http://85.215.219.243:5000"
AUTH_TOKEN = "zhmwsdl<3"
POLL_INTERVAL = 1.0  # Prüft jede Sekunde nach WLAN-Befehlen vom Server

def scan_wifi():
    print("[WiFi] Starte rohen Hardware-Scan (Bypass Cache)...")
    try:
        # Wir zwingen die Hardware direkt über 'iwlist' alle Kanäle zu scannen
        scan_output = subprocess.check_output(
            ['sudo', 'iwlist', 'wlan0', 'scan'], 
            stderr=subprocess.STDOUT
        ).decode('utf-8')
        
        ssids = []
        for line in scan_output.split('\n'):
            if 'ESSID:' in line:
                # Isoliert den Netzwerknamen zwischen den Anführungszeichen
                ssid = line.split('ESSID:"')[1].split('"')[0].strip()
                
                # Leere oder versteckte Netzwerke ignorieren (\x00)
                if ssid and ssid not in ssids and "\\x00" not in ssid:
                    ssids.append(ssid)

        print(f"[WiFi] Hardware-Scan beendet. Sende {len(ssids)} Netzwerke an den Server...")
        requests.post(f"{SERVER_URL}/api/wifi/set_results", json={"networks": ssids}, timeout=3)
        
    except Exception as e:
        print(f"[WiFi] Fehler beim Hardware-Scan: {e}")
        # Notfall-Fallback, falls iwlist blockiert sein sollte
        try:
            print("[WiFi] Versuche Fallback über nmcli...")
            result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi']).decode('utf-8')
            ssids = list(set([line.strip() for line in result.split('\n') if line.strip()]))
            requests.post(f"{SERVER_URL}/api/wifi/set_results", json={"networks": ssids}, timeout=3)
        except Exception as ex:
            print(f"[WiFi] Fallback ebenfalls fehlgeschlagen: {ex}")

def connect_wifi(ssid, pw):
    print(f"[WiFi] Versuche Verbindung mit '{ssid}'...")
    try:
        # Für das Verbinden nutzen wir weiterhin nmcli, da er die Passwörter verwaltet
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