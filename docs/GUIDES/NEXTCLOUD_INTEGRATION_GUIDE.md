# 🔗 Nextcloud Integration - Vollständiger Setup-Guide

## 📋 Überblick

Die MYND-Anwendung kann sich mit deiner **Nextcloud-Instanz** verbinden, um:
- 📄 Dokumente zu indexieren und durchsuchbar zu machen
- 📅 Kalender-Events zu laden und anzuzeigen
- ✅ Aufgaben zu verwalten
- 📸 Fotos über Immich zu integrieren (optional)

---

## ⚠️ Das Problem: "Error: No active login flow"

Diese Fehlermeldung tritt auf, wenn:

1. **❌ WICHTIGST:** Die Nextcloud-URL ist noch auf `https://nextcloud.example.com` (Placeholder)
2. Das Backend kann sich nicht zu dieser URL verbinden
3. Daher schlägt der Login-Flow fehl
4. Die Session-Variablen werden nicht gespeichert

**Die Lösung: Echte Nextcloud-URL konfigurieren!**

---

## 🚀 Quick Start (3 Schritte)

### 1️⃣ Nextcloud-URL konfigurieren

Führe das Setup-Script aus:

```bash
cd /path/to/mynd
python3 scripts/setup/setup_nextcloud.py
```

Das Script wird dich folgende Schritte leiten:
- ✓ Validiert deine Nextcloud-URL
- ✓ Testet die Verbindung
- ✓ Speichert die Konfiguration
- ✓ Richtet Umgebungsvariablen ein

### 2️⃣ Backend und Frontend starten

**Terminal 1 - Backend:**
```bash
cd backend/core
python3 app.py
# Output sollte zeigen: "Running on http://0.0.0.0:5001"
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
# Output sollte zeigen: "ready on http://localhost:3000"
```

### 3️⃣ Nextcloud verbinden

1. Öffne **http://localhost:3000** im Browser
2. Navigiere zu **Integrationen** oder **Dokumente**
3. Klicke auf **"Mit Nextcloud verbinden"**
4. Gib deine **Nextcloud-URL** ein (z.B. `https://nextcloud.example.com`)
5. Klicke **"Anmelden"**
6. Du wirst zu deiner Nextcloud weitergeleitet
7. Melde dich an und autorisiere MYND
8. ✓ Die Verbindung ist hergestellt!

---

## 📝 Manuelle Konfiguration

Falls das Script nicht funktioniert, kannst du die Konfiguration manuell durchführen:

### Schritt 1: Nextcloud-Datei aktualisieren

Bearbeite `backend/config/nextcloud_config.json`:

```json
{
  "nextcloud_url": "https://your-nextcloud-domain.com",
  "username": "USE_ENV_VARIABLE_NEXTCLOUD_USERNAME",
  "password": "USE_ENV_VARIABLE_NEXTCLOUD_PASSWORD",
  "auth_type": "login_flow_v2",
  "display_name": "USE_ENV_VARIABLE_NEXTCLOUD_DISPLAY_NAME"
}
```

**Wichtig:** Ersetze `your-nextcloud-domain.com` mit deiner echten Nextcloud-URL!

### Schritt 2: Umgebungsvariablen setzen

Bearbeite `.env`:

```env
NEXTCLOUD_USERNAME=dein_benutzername
NEXTCLOUD_PASSWORD=dein_app_passwort
NEXTCLOUD_DISPLAY_NAME=Mein MYND Assistant
```

**Hinweis:** Verwende ein **App-Passwort**, kein normales Passwort!
- In Nextcloud: **Einstellungen > Sicherheit > App-Passwörter**

### Schritt 3: Backend neustarten

```bash
cd backend/core
python3 app.py
```

---

## 🔐 Nextcloud App-Passwort erstellen

**Warum ein App-Passwort?**
- ✓ Sicherer als dein Hauptpasswort
- ✓ Kann gezielt widerrufen werden
- ✓ Begrenzte Berechtigungen
- ✓ Nicht in deinem Hauptpasswort gespeichert

**Wie erstelle ich ein App-Passwort?**

1. Öffne deine Nextcloud-Instanz
2. Klicke auf dein Profilbild (oben rechts)
3. Gehe zu **Einstellungen**
4. Wähle **Sicherheit**
5. Scrollen zu **App-Passwörter**
6. Gib einen Namen ein (z.B. "MYND Assistant")
7. Klicke **"Passwort generieren"**
8. Kopiere das generierte Passwort
9. Verwende dieses Passwort in `.env`

---

## 🔄 Nextcloud Login Flow v2 (OAuth2-ähnlich)

### Wie funktioniert der Login-Flow?

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   MYND UI   │────────▶│  MYND Backend    │────────▶│  Nextcloud      │
│  (Frontend) │         │                  │         │  Instance       │
└─────────────┘         └──────────────────┘         └─────────────────┘
       │                         │                           │
       │  1. User clicks         │                           │
       │  "Connect Nextcloud"    │                           │
       ├────────────────────────▶│                           │
       │                         │  2. POST /login/v2        │
       │                         ├──────────────────────────▶│
       │                         │                           │
       │                         │  3. Erhalte login_url     │
       │                         │  + poll_token             │
       │                         │◀──────────────────────────┤
       │  4. Redirect to         │                           │
       │  Nextcloud Login        │                           │
       │◀────────────────────────┤                           │
       │                         │                           │
       │  5. User logs in        │                           │
       │  and grants permission  │                           │
       ├────────────────────────────────────────────────────▶│
       │                         │                           │
       │                         │  6. Poll /login/v2        │
       │                         ──────────────────────────▶│
       │                         │                           │
       │                         │  7. Return app password   │
       │                         │  + login name             │
       │                         │◀──────────────────────────┤
       │  8. Set credentials     │                           │
       │◀────────────────────────┤                           │
       │  ✓ Connected!           │                           │
       │                         │                           │
```

### Session-Verwaltung

Das Backend speichert wichtige Daten in der **Session** (Flask):

```python
session['loginflow_nextcloud_url'] = 'https://nextcloud.example.com'
session['loginflow_poll_token'] = 'abc123token'
session['loginflow_poll_endpoint'] = 'https://nextcloud.example.com/index.php/login/v2/poll'
```

Diese werden nach erfolgreicher Authentifizierung gelöscht.

---

## 🏗️ Authentifizierungs-Methoden

### 1. **Login Flow v2** (Empfohlen ⭐)

- **Flow:** Benutzer meldet sich bei Nextcloud an
- **Ergebnis:** App-Spezifisches Passwort
- **Sicherheit:** Hoch (kein Passwort im Backend!)
- **Verwendung:** Im UI "Mit Nextcloud verbinden"

### 2. **Direct Auth** (Fallback)

- **Methode:** Benutzername + Passwort direkt
- **Sicherheit:** Medium (Credentials müssen gespeichert sein)
- **Verwendung:** Nur wenn Login Flow nicht verfügbar

### 3. **OAuth2** (Zukünftig)

- **Flow:** Standard OAuth2
- **Voraussetzung:** OAuth2-App in Nextcloud registriert
- **Sicherheit:** Sehr hoch (Refresh Tokens)

---

## ❌ Häufige Fehler und Lösungen

### Fehler: "No active login flow"

**Ursache:** Nextcloud-URL ist nicht konfiguriert oder nicht erreichbar

**Lösung:**
```bash
# 1. Überprüfe die Konfiguration
cat backend/config/nextcloud_config.json

# 2. Testiere die URL manuell
curl https://your-nextcloud-url/status.php

# 3. Führe Setup-Script aus
python3 scripts/setup/setup_nextcloud.py
```

### Fehler: "Invalid Nextcloud instance"

**Ursache:** Die URL zeigt nicht auf eine gültige Nextcloud-Instanz

**Lösung:**
```bash
# Teste den Status-Endpoint
curl https://your-nextcloud-url/status.php | json_pp

# Sollte anzeigen: "installed": true
```

### Fehler: "Connection timed out"

**Ursache:** Backend kann URL erreichen (Netzwerk-Problem)

**Lösung:**
- ✓ Prüfe ob Nextcloud-Server läuft
- ✓ Prüfe ob die URL erreichbar ist
- ✓ Prüfe Firewall-Regeln
- ✓ Prüfe SSL-Zertifikat (validating ist wichtig!)

### Fehler: "State mismatch"

**Ursache:** CSRF-Schutz hat einen ungültigen Session-State erkannt

**Lösung:**
- ✓ Löscht Browser-Cookies
- ✓ Startet Backend neu
- ✓ Versucht erneut

---

## 🧪 Integration testen

### Backend-Endpunkte überprüfen

```bash
python3 scripts/setup/check_backend_endpoints.py
```

Sollte zeigen:
```
[POST] http://localhost:5001/api/nextcloud/loginflow/start
  ✓ Status: 200

[GET] http://localhost:5001/api/nextcloud/loginflow/poll
  ✓ Status: 400 (normal - kein aktiver Fluss)
```

### Manuell testen mit curl

```bash
# 1. Starte Login Flow
curl -X POST http://localhost:5001/api/nextcloud/loginflow/start \
  -H "Content-Type: application/json" \
  -d '{"nextcloud_url": "https://your-nextcloud-url"}'

# Sollte zurückgeben:
# {
#   "status": "started",
#   "login_url": "https://your-nextcloud-url/index.php/login/v2?state=..."
# }

# 2. Poll für Erfolg (nach Benutzer-Authentifizierung)
curl http://localhost:5001/api/nextcloud/loginflow/poll

# Sollte zurückgeben:
# {
#   "status": "connected",
#   "username": "your_username",
#   "nextcloud_url": "https://your-nextcloud-url"
# }
```

---

## 📚 Weitere Ressourcen

- [Nextcloud Documentation](https://docs.nextcloud.com/)
- [Nextcloud Login Flow v2](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/LoginFlow/index.html#login-flow-v2)
- [App Passwords](https://docs.nextcloud.com/server/latest/user_manual/en/session_management.html#managing-devices)

---

## 🆘 Support

Wenn du weitere Probleme hast:

1. **Überprüfe die Logs:**
   ```bash
   # Backend-Logs
   tail -f /tmp/mynd_backend.log
   
   # Frontend-Logs (Browser Console)
   F12 > Console Tab
   ```

2. **Überprüfe die Konfiguration:**
   ```bash
   cat backend/config/nextcloud_config.json
   cat .env
   ```

3. **Testet Backend-Verbindung:**
   ```bash
   python3 scripts/setup/check_backend_endpoints.py
   ```

---

**Viel Erfolg beim Einrichten!** 🎉
