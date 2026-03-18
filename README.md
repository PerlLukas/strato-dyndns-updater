# DynDNS-Updater für Strato

Dieses Projekt enthält ein Python-Skript, das die aktuelle öffentliche IP-Adresse eines Servers oder Heimanschlusses prüft und den DynDNS-Eintrag bei Strato nur dann aktualisiert, wenn sich die IP geändert hat.

Das Skript unterstützt IPv4 und IPv6, schreibt Logdateien in ein lokales `logs/`-Verzeichnis und lässt sich bequem über `systemd` und einen Timer regelmäßig ausführen.

Normale Läufe landen in einer Tagesdatei wie `26_03_18.log`. Wenn während eines Laufs ein Fehler auftritt oder Strato eine fehlerhafte Antwort wie `nohost` zurückgibt, wird die Datei als `26_03_18_error.log` geführt.

## Hinweis / Disclaimer

Dieses Projekt steht in keiner Verbindung zu Strato AG und wird von Strato weder unterstützt noch offiziell bereitgestellt.

Die Nutzung erfolgt vollständig auf eigene Verantwortung. Für Fehlkonfigurationen, Ausfälle, falsche DNS-Einträge oder sonstige Schäden wird keine Haftung übernommen.

Zum Ermitteln der öffentlichen IP-Adressen verwendet das Skript aktuell die externen Endpunkte `https://api.ipify.org` und `https://api6.ipify.org`. Dabei wird keine zusätzliche Verarbeitung oder Speicherung durch dieses Projekt vorgenommen. Trotzdem können die angesprochenen Dienste oder deren Infrastruktur- beziehungsweise Cloud-Anbieter Verbindungsdaten die IP-Adresse serverseitig protokollieren.

Wenn du das nicht möchtest, kannst du in [main.py](/home/website/code/dynDNS/main.py) die Funktionen `get_public_ipv4()` und `get_public_ipv6()` auf eigene Endpunkte umstellen. Wichtig ist nur, dass der jeweilige Endpoint als Antwort ausschließlich die IP-Adresse als reinen Text zurückgibt.

## Funktionen

- Abgleich der aktuellen öffentlichen IPv4- und IPv6-Adresse
- Vergleich mit den aktuell für die Domain aufgelösten DNS-Einträgen
- DynDNS-Update nur bei Abweichungen
- Protokollierung in Logdateien
- Geeignet für den automatischen Betrieb mit `systemd`

## Projektstruktur

```text
dynDNS/
|- main.py
|- logs/
`- README.md
```

## Voraussetzungen

- Python 3
- Linux-System mit `systemd`
- Ein aktiver DynDNS-Eintrag bei Strato

Versionen prüfen:

```bash
python3 --version
systemctl --version
```

## Konfiguration

### 1. Domain im Skript anpassen

In [`main.py`](/home/website/code/dynDNS/main.py) ist aktuell ein Platzhalter eingetragen:

```python
DOMAIN = "example.com"
```

Diesen Wert musst du durch deine eigene Domain oder Subdomain ersetzen, die bei Strato per DynDNS aktualisiert werden soll.

### 2. Zugangsdaten in externer Datei speichern

Die Zugangsdaten gehören nicht in den Python-Code und sollten extra gesichert abgelegt werden

Erstelle dafür die Datei `/etc/dyndns.conf`:

```bash
sudo nano /etc/dyndns.conf
```

Inhalt:

```ini
USERNAME=DEIN_STRATO_USERNAME
PASSWORD=DEIN_STRATO_PASSWORT
```

Dateirechte absichern:

```bash
sudo chown <user>:<user> /etc/dyndns.conf
sudo chmod 600 /etc/dyndns.conf
```

Prüfen:

```bash
ls -l /etc/dyndns.conf
```

Erwartet wird sinngemäß:

```text
-rw------- 1 <user> <user> ... /etc/dyndns.conf
```

## Skript vorbereiten

Beispielpfad des Projekts:

```text
/home/<user>/code/dynDNS/
```

Das Skript ausführbar machen:

```bash
chmod +x /home/<user>/code/dynDNS/main.py
```

Testlauf:

```bash
sudo python3 /home/<user>/code/dynDNS/main.py
```

## Automatisierung mit systemd

### 1. Service-Datei erstellen

Datei anlegen:

```bash
sudo nano /etc/systemd/system/dyndns.service
```

Inhalt:

```ini
[Unit]
Description=DynDNS IP Check Script

[Service]
Type=oneshot
User=<user>
ExecStart=/usr/bin/sudo /usr/bin/python3 /home/<user>/code/dynDNS/main.py
```

Der Service führt das Skript einmal aus und beendet sich danach. Das ist hier nötig, weil das Skript die Datei `/etc/dyndns.conf` liest und dafür in deiner aktuellen Konfiguration `sudo` benötigt wird.

### 2. Timer-Datei erstellen

Datei anlegen:

```bash
sudo nano /etc/systemd/system/dyndns.timer
```

Inhalt:

```ini
[Unit]
Description=Run DynDNS check every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Unit=dyndns.service

[Install]
WantedBy=timers.target
```

Bedeutung:

- erster Start eine Minute nach dem Booten
- danach alle fünf Minuten

### 3. systemd neu laden und Timer aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dyndns.timer
```

## Status und Logs prüfen

Timerstatus:

```bash
systemctl status dyndns.timer
```

Alle Timer anzeigen:

```bash
systemctl list-timers
```

Service manuell starten:

```bash
sudo systemctl start dyndns.service
```

Service-Status:

```bash
systemctl status dyndns.service
```

Journal-Logs:

```bash
journalctl -u dyndns.service
```

Nur die letzten Einträge:

```bash
journalctl -u dyndns.service -n 20
```

Lokale Python-Logs liegen in:

```text
/home/<user>/code/dynDNS/logs/
```

Beispielnamen:

```text
26_03_18.log
26_03_18_error.log
```

## Timer deaktivieren

```bash
sudo systemctl stop dyndns.timer
sudo systemctl disable dyndns.timer
```

## Typische Probleme

### `PermissionError` bei `/etc/dyndns.conf`

Wenn das Skript die Konfigurationsdatei nicht lesen kann, prüfe Eigentümer und Rechte:

```bash
sudo chown <user>:<user> /etc/dyndns.conf
sudo chmod 600 /etc/dyndns.conf
```

Wenn du das Skript manuell startest, verwende in dieser Konfiguration ebenfalls `sudo`:

```bash
sudo python3 /home/<user>/code/dynDNS/main.py
```

### Timer läuft nicht automatisch

Prüfen, ob der Timer geladen wurde:

```bash
systemctl list-timers
```

Wenn `dyndns.timer` fehlt:

```bash
sudo systemctl enable --now dyndns.timer
```

## Sicherheitshinweise

- Zugangsdaten niemals im Quellcode speichern
- Die Datei `/etc/dyndns.conf` nur für den benötigten Benutzer lesbar machen
- Wenn `/etc/dyndns.conf` nur mit erhöhten Rechten lesbar ist, das Skript bewusst per `sudo` ausführen
- Logdateien regelmäßig kontrollieren
