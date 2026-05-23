# MYND — Admin Setup & Security Checklist

Diese Anleitung beschreibt kurz die wichtigsten Schritte, um die Admin-Funktionalität sicher in Betrieb zu nehmen.

## 1) Abhängigkeiten installieren

Im Backend-Ordner:

```bash
pip install -r backend/requirements.txt
```

## 2) Wichtige Umgebungsvariablen

- `ADMIN_USER`: Name des Administrators (Standard: `admin`). Nur dieser Benutzer darf Admin-APIs nutzen.
- `JWT_SECRET`: gemeinsames Geheimnis für JWT-Signierung (falls nicht gesetzt, wird `FLASK_SECRET_KEY` verwendet).
- `AUTH_COOKIE_SECURE=true`: In Produktion setzen und HTTPS verwenden.
- `NEXTCLOUD_ACCOUNTS_KEY`: Base64 url-safe 32-byte Fernet-Key zur Verschlüsselung gespeicherter Nextcloud-Konten. Wenn nicht gesetzt, wird ein Key aus `JWT_SECRET` abgeleitet (weniger sicher).

Beispiel, um einen Schlüssel lokal zu erzeugen:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Speichere den Key sicher (Password-Manager, Vault).

## 3) Admin-UI benutzen

Öffne die App und melde dich als `ADMIN_USER` an (Login in der App). Dann rufe `/admin` auf.

Funktionen:
- Nutzer anlegen (`Neuen Nutzer anlegen`)
- Passwort zurücksetzen (`Passwort zurücksetzen`)
- Nutzer löschen (Löschen-Button neben Nutzer)
- Nextcloud-Konten anzeigen und löschen
- Key-Rotation: neues `NEXTCLOUD_ACCOUNTS_KEY` eingeben und auf "Key rotieren" klicken

Hinweis: Die Admin-UI ist nur über Auth geschützt — stelle sicher, dass dein Admin-Account sicher ist.

## 4) Nextcloud OAuth

- Registriere eine OAuth-App in deiner Nextcloud-Instanz und hole `client_id` und `client_secret`.
- Setze `NEXTCLOUD_OAUTH_CLIENT_ID` und `NEXTCLOUD_OAUTH_CLIENT_SECRET` in deiner Umgebung.
- Beim Login über Nextcloud fragt die App nach der Domain. Nach erfolgreichem Login werden die Zugangsdaten verschlüsselt gespeichert.

## 5) Key Rotation & Backup

- Backup: Sichere `backend/config/nextcloud_accounts.json` nach jeder Änderung (verschlüsselt).
- Rotate: In der Admin-UI kannst du einen neuen Base64-Key angeben; das System versucht, die Konten mit dem neuen Key zu re-sichern.

## 6) Empfehlungen für Produktion

- Verwende HTTPS und setze `AUTH_COOKIE_SECURE=true`.
- Verwende ein zentrales Secret-Management (Vault) für `NEXTCLOUD_ACCOUNTS_KEY` und `JWT_SECRET`.
- Erstelle mindestens einen Admin und sichere dessen Zugang (starkes Passwort, 2FA wenn möglich).
- Richte Monitoring/Logging (z. B. Sentry, Prometheus) für das Backend ein.

## 7) Troubleshooting

- Bei Problemen mit OAuth: prüfe Backend-Logs (`run_app.py` stdout) auf Tracebacks.
- Bei Entschlüsselungsfehlern: stelle sicher, dass `NEXTCLOUD_ACCOUNTS_KEY` korrekt ist; bei Bedarf importiere/exportiere Konten und rotiere den Key.

---

Wenn du möchtest, erstelle ich noch ein kurzes Skript, das einen neuen `NEXTCLOUD_ACCOUNTS_KEY` generiert und in eine `.env`-Datei schreibt.
