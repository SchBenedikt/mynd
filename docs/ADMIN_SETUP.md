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

## Produktions-Deployment (Docker)

Diese Anleitung beschreibt empfohlene Schritte, um MYND produktiv mit `docker compose -f docker-compose.prod.yml` zu betreiben, inklusive Reverse-Proxy, TLS, Backups und Wartung.

### 1) Prinzipielle Architektur
- Container: `backend` (Flask), `frontend` (Next.js). Siehe `docker-compose.prod.yml` für Ports und Volumes.
- Externer LLM-Host: Ollama — muss für Backend erreichbar sein (`OLLAMA_BASE_URL`).
- Reverse-Proxy (empfohlen): nginx, Caddy oder Traefik vor den Containern für TLS, Auth-Header und Rate-Limiting.

### 2) Vorbereitung: `.env`-Datei
Lege eine `.env.prod` mit sicheren Werten an (nicht ins VCS!). Beispiel:

```bash
FLASK_SECRET_KEY=change-this-to-a-long-random-value
JWT_SECRET=another-secret-if-needed
NEXTCLOUD_ACCOUNTS_KEY=<base64-fernet-key>
OLLAMA_BASE_URL=http://ollama.example.local:11434
AUTH_COOKIE_SECURE=true
# Optional: NEXT_PUBLIC_BACKEND_URL for frontend build-time
NEXT_PUBLIC_BACKEND_URL=https://mynd.example.com
```

Starte die Compose-Stacks mit:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

### 3) Reverse-Proxy & TLS (nginx-Beispiel)
Empfehlung: Proxy setzt `X-Forwarded-*` Headers und terminiert TLS. Beispielkonfiguration (auszugsweise):

```nginx
server {
	listen 80;
	server_name mynd.example.com;
	location / {
		return 301 https://$host$request_uri;
	}
}

server {
	listen 443 ssl;
	server_name mynd.example.com;
	ssl_certificate /etc/letsencrypt/live/mynd.example.com/fullchain.pem;
	ssl_certificate_key /etc/letsencrypt/live/mynd.example.com/privkey.pem;

	location / {
		proxy_pass http://localhost:3001; # Frontend
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
	}
}
```

Wenn du Backend-API direkt erreichbar machen willst, routen `api/*` an `http://localhost:5001` oder lasse Next.js Proxying wie in dev.

### 4) Volumes, Persistenz und Backups
- Persistente Volumes per `docker volume` (siehe `docker-compose.prod.yml`): `mynd-data` und `mynd-backend-config`.
- Wichtige Dateien: `data/knowledge_base.db`, `backend/config/` (Nextcloud-Konten, ai_config).

Backup-Strategie (SQLite):

```bash
# stoppe Container oder nutze sqlite3 .backup
docker compose -f docker-compose.prod.yml exec backend sh -c "sqlite3 /app/data/knowledge_base.db '.backup /tmp/knowledge_base.db' && cp /tmp/knowledge_base.db /backup/location/knowledge_db_$(date +%F).db"
```

Alternativ das Volume mounten und von Host aus kopieren:

```bash
docker run --rm -v mynd-data:/data -v $(pwd)/backups:/backup alpine sh -c "cp /data/knowledge_base.db /backup/knowledge_db_$(date +%F).db"
```

Automatisiere Backups per Cronjob/CI (z. B. täglicher Cron in einem separaten Container) und verifiziere Backups regelmäßig.

### 5) Key-Rotation & Recovery
- Key-Rotation: Erzeuge neuen `NEXTCLOUD_ACCOUNTS_KEY`, setze ihn in `.env`, starte Container neu und nutze Admin-UI `Key rotieren` falls verfügbar.
- Recovery: Vor Rotation immer vollständiges Backup von `backend/config/` und `data/` anfertigen.

### 6) Logging, Monitoring, Healthchecks
- Weiterleiten von Logs an einen zentralen Log-Stack (journald, filebeat, ELK, Grafana Loki) empfohlen.
- Healthchecks: Füge einfache HTTP-Endpoints (`/api/knowledge/status`, `/api/ollama/status`) als Docker Healthcheck oder Prometheus-Exporter hinzu.

Beispiel Docker-Healthcheck-Snippet in `docker-compose.prod.yml` (optional):

```yaml
healthcheck:
	test: ["CMD", "curl", "-f", "http://localhost:5001/api/knowledge/status"]
	interval: 1m
	timeout: 10s
	retries: 3
```

### 7) Updates & Wartung
- Update-Workflow:
	1. Backup erstellen (Daten + config)
	2. `docker compose pull` (falls Images extern)
	3. `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`
	4. Prüfe Logs: `docker compose -f docker-compose.prod.yml logs -f backend`
- Für Zero-downtime: nutze Rolling-Recreate mit Swarm/Kubernetes oder baue Blue-Green-Deployment um den Proxy.

### 8) Sicherheitsempfehlungen
- HTTPS zwingend für öffentliche Dienste
- Setze `AUTH_COOKIE_SECURE=true` und `SameSite=Lax/Strict`
- Schütze Admin-Accounts mit starken Passwörtern; 2FA falls möglich
- Secrets in Vault oder Umgebung speichern, nicht im Repo
- Beschränke Zugriff auf Ollama-Netzwerk auf interne Hosts

### 9) Skalierung
- MYND ist nicht für horizontale Skalierung der SQLite-Datenbank ausgelegt. Für hohe Skalierung: extrahiere Persistenz aus SQLite (z. B. Postgres) und passe `backend/core/database.py` entsprechend.

## Kurze Checkliste vor Go-Live
- [. ] `.env.prod` mit sicheren Werten
- [. ] Backups und Backup-Rotate eingerichtet
- [. ] TLS via Reverse-Proxy konfiguriert
- [. ] Monitoring/Alerting eingerichtet
- [. ] Healthchecks implementiert
- [. ] Admin-Account gesichert (starkes Passwort)

---

Wenn du möchtest, kann ich:
- ein `deploy`-Shellskript generieren, das `.env.prod` validiert, Backups vor Updates macht und den Compose-Stack neu startet; oder
- eine Beispiel-nginx- und Let's-Encrypt-Setupdatei erstellen; oder
- ein GitHub Actions Workflow-Template für CI/CD erstellen.
