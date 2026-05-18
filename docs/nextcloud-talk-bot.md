### Nextcloud Talk: Bot- & Webhook-Anleitung (Web‑UI)

Kurz: Diese Anleitung ist für die Mynd-Weboberfläche gedacht. Die Secrets werden dort eingetragen und gespeichert. `.env` ist nur für spezielle Self-Hosting- oder Deployment-Setups relevant, nicht der Standardweg für Endnutzer.

Voraussetzungen
- Du bist Nextcloud‑Admin oder Raum‑Besitzer.
- Talk‑App und Talk‑Integrationen sind aktiviert.

1) Bot‑Benutzer anlegen (Admin UI)
- Admin → Einstellungen → Benutzer → "Neuen Benutzer erstellen".
- Benutzername z. B. `mynd-bot`, Anzeigename `Mynd Bot`.
- Passwort temporär setzen.

2) App‑Passwort für den Bot
- Melde dich als der Bot‑User an (oder bitte den Bot‑Owner, sich anzumelden).
- Einstellungen (rechts oben) → Sicherheit → "App‑Passwörter" → neues App‑Passwort erzeugen.
- Kopiere den angezeigten Wert sofort (wird nur einmal angezeigt).

3) Room‑Token / Room‑ID finden (für Nutzer)
- Nextcloud → Talk → gewünschten Raum öffnen.
- Drei Punkte / "Info" / "Teilen/Einladen" → Einladungs‑Link oder Browser‑URL kopieren.
- Beispiel: `https://cloud.example.com/apps/talk/o/ofexbgra` → `ofexbgra` ist das Raum‑Token/ID.

4) Incoming Webhook im Raum anlegen (Web UI)
- Im Raum: drei Punkte → "Integrationen" (oder "Einstellungen → Integrationen").
- "Integration hinzufügen" → "Incoming Webhook" (Name vergeben) → erstellen.
- Kopiere die Webhook‑URL und ggf. das Secret sofort (wird oft nur einmal gezeigt).

Hinweis: Falls "Incoming Webhook" nicht sichtbar ist → Admin → Apps → Talk/Integrationen aktivieren.

5) Secrets in Mynd speichern
- Öffne in Mynd die Nextcloud-Talk-Einstellungen und trage Raum-Slug, Bot-ID und Secret direkt in der Web-Oberfläche ein.
- Mynd speichert das Secret serverseitig; du musst dafür nicht mit `.env` arbeiten.
- Nur wenn du Mynd komplett headless oder automatisiert betreibst, sind Umgebungsvariablen oder Secret-Stores eine Option.

6) Kurzer Test (Webhook)
```
curl -X POST -H "Content-Type: application/json" \
  -d '{"message":"Test von Mynd"}' \
  'DEINE_WEBHOOK_URL'
```

7) Alternativer Test: Bot per API (App‑Passwort)
```
curl -u "mynd-bot:APP_PASSWORD" -H "OCS-APIRequest: true" -H "Accept: application/json" \
  -X POST "https://cloud.example.com/ocs/v2.php/apps/spreed/api/v1/chat/ROOM_TOKEN/message" \
  -d '{"message":"Hallo vom Bot"}'
```
Hinweis: Endpoints/Body sind versionsabhängig; bei 404 zuerst `GET /ocs/v2.php/apps/spreed/api/v1/room` prüfen.

8) Security‑Tipps (kurz)
- Nutze App‑Passwort statt Hauptpasswort.
- Verwende einen separaten Bot‑Account mit minimalen Rechten.
- Speichere Webhook‑URL/Secrets in Mynd oder in einem Secret‑Store, nicht im Repository.
- Drehe Secrets, wenn sie kompromittiert wurden.

Wenn du möchtest, kann ich die Anleitung noch als eigene Hilfeseite im Frontend verlinken oder als ausklappbaren Tooltip direkt bei den Feldern anzeigen.
