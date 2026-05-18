# Nextcloud Talk Bot Setup Guide

## 📌 Überblick

Diese Anleitung zeigt Schritt-für-Schritt, wie du den **Mynd Talk Bot** auf deinem Nextcloud-Server installierst und konfigurierst. Der Bot kann dann in Nextcloud Talk Räumen Nachrichten beantworten.

**Voraussetzungen:**
- ✅ SSH-Zugriff zu deinem Nextcloud-Server mit **Admin-Rechten**
- ✅ Mynd Backend läuft und ist über eine **öffentliche URL** erreichbar (z.B. `https://mynd.example.com/api/nextcloud/talk/webhook`)
- ✅ Firewall erlaubt externe HTTPS-Requests von Nextcloud zu Mynd

---

## 🚀 Schritt-für-Schritt Setup

### **Schritt 1: Webhook-URL konfigurieren**

In Mynd **Settings → Talk Bot Setup** → Feld "Webhook-URL von Mynd":
- Trage die öffentliche URL deines Mynd-Backends ein
- Beispiel: `https://mynd.example.com/api/nextcloud/talk/webhook`
- Die URL MUSS von außen erreichbar sein (nicht localhost!)

**Lokale Entwicklung?** Nutze **ngrok** oder **Cloudflare Tunnel**:
```bash
# Mit ngrok
ngrok http 5001

# Mit Cloudflare Tunnel
cloudflare tunnel run mynd-tunnel
```

---

### **Schritt 2: Bot-Secret generieren**

Im Feld "Bot-Secret generieren" in Mynd Settings:
1. Öffne ein SSH-Terminal auf deinem **Nextcloud-Server**
2. Führe aus:
   ```bash
   openssl rand -hex 24
   ```
3. Du erhältst eine 48-Zeichen lange Zeichenkette (z.B. `a1b2c3d4e5f6...`)
4. Kopiere das Secret in das Feld "Bot-Secret generieren" in Mynd Settings
5. Klick Copy-Button um das Secret zu speichern

**ℹ️ Das Secret muss später exakt ins OCC-Setup und in Mynd Settings stimmen!**

---

### **Schritt 3: Bot auf Nextcloud installieren**

In Mynd **Settings → Talk Bot Setup** → "Bot auf Nextcloud installieren":

1. Der Befehl wird automatisch mit deiner **Webhook-URL** und deinem **Secret** gefüllt
2. Kopiere den Befehl (klick "📋 Befehl kopieren")
3. Öffne SSH zu deinem **Nextcloud-Server** und führe aus:
   ```bash
   sudo -u www-data php /var/www/nextcloud/occ talk:bot:install \
     --feature response --no-setup \
     "Mynd Bot" \
     "<SECRET>" \
     "<WEBHOOK-URL>"
   ```
   (Die Werte sind bereits im Mynd-UI vorgefüllt!)

4. Der Befehl gibt eine **Bot‑ID** direkt in der Ausgabe aus (z.B. `ID: 40` oder als längere Kennung). **Speichere diese!**
   ```
   Bot installed
   ID: 40
   ```

---

### **Schritt 4: Bot-ID abrufen**

Wenn du die Bot‑ID aus Schritt 3 verloren hast oder sie nicht angezeigt wurde, führe aus:
```bash
sudo -u www-data php /var/www/nextcloud/occ talk:bot:list
```

Suche nach "Mynd Bot" und kopiere die Bot-ID (erste Spalte).

Oder in Mynd Settings: Gebe die Bot-ID in das Feld "Bot-ID abrufen" ein.

---

### **Schritt 5: Bot zu Nextcloud-Raum hinzufügen**

In Mynd **Settings → Talk Bot Setup** → "Bot zum Raum hinzufügen":

1. Gebe den **Room-Token** ein (z.B. `ofexbgra`)
   - Den Room-Token findest du in der URL: `https://nc.example.com/apps/spreed/?token=OFEXBGRA`
2. Der Befehl wird automatisch gefüllt
3. Kopiere: "📋 Befehl kopieren"
4. SSH zu Nextcloud-Server:
   ```bash
   sudo -u www-data php /var/www/nextcloud/occ talk:bot:setup \
     "<BOT_ID>" \
     "<ROOM_TOKEN>"
   ```

**✅ Der Bot ist jetzt im Raum registriert!**

---

### **Schritt 6: Secret in Mynd speichern**

In Mynd **Settings → Talk Bot Setup** → "Secret in Mynd speichern":

1. Gebe das exakt gleiche Secret ein wie in **Schritt 2**
2. Klick "💾 Secret speichern"
3. Du solltest sehen: "✅ Secret ist gespeichert"

**⚠️ WICHTIG:** Das Secret MUSS exakt mit dem OCC-Setup übereinstimmen!

---

### **Schritt 7: Webhook testen**

In Mynd **Settings → Talk Bot Setup** → "Webhook testen":

1. Klick "🧪 Talk Webhook testen"
2. **Erfolg?** ✅ "Bot ist aktiv!" → Alle Setup-Schritte waren korrekt
3. **Fehler?** ❌ Lies die Fehlermeldung:
   - **401 Signature Error** → Secret falsch/nicht gespeichert
   - **404 Not Found** → Webhook-URL nicht erreichbar
   - **Bot not installed** → OCC install fehlgeschlagen

---

## 🧪 Live-Test

Jetzt kannst du den Bot testen:

1. **Öffne Nextcloud Talk** → der Raum, in dem du den Bot eingerichtet hast
2. **Schreibe eine Nachricht** (z.B. "Hallo bot, wie geht es dir?")
3. **Warte 2-5 Sekunden**
4. **Der Bot sollte antworten** mit seiner Identität "Mynd Bot" (nicht unter deinem Username!)

---

## ❌ Troubleshooting

### **Fehler: "❌ Signatur-Fehler: Bot-Secret ist falsch"**

**Ursache:** Das Secret in Mynd Settings stimmt nicht mit dem OCC-Setup überein

**Lösung:**
1. SSH zu Nextcloud-Server
2. Zeige den Bot: `sudo -u www-data php /var/www/nextcloud/occ talk:bot:list`
3. Kopiere den Secret-Hash (nicht die Bot-ID!)
4. Vergleiche mit dem Secret in Mynd Settings
5. Wenn unterschiedlich: Speichere das richtige Secret in Mynd

---

### **Fehler: "❌ Bot-Authentifizierung fehlgeschlagen (401)"**

**Ursache:** Bot ist nicht korrekt auf dem Nextcloud-Server installiert

**Lösung:**
1. SSH zu Nextcloud-Server
2. Prüfe ob Bot existiert: `sudo -u www-data php /var/www/nextcloud/occ talk:bot:list`
3. Wenn nicht vorhanden: Führe Schritt 3 erneut aus
4. Wenn vorhanden: Prüfe die Logs auf Nextcloud:
   ```bash
   tail -50 /var/www/nextcloud/data/nextcloud.log | grep -i bot
   ```

---

### **Fehler: "❌ Endpoint nicht gefunden (404)"**

**Ursache:** Webhook-URL ist nicht erreichbar

**Lösung:**
1. Prüfe ob Mynd-Backend läuft:
   ```bash
   curl -I https://mynd.example.com/api/nextcloud/talk/webhook
   ```
2. Sollte 400 oder 401 antworten (nicht 404)
3. Prüfe Firewall/DNS:
   ```bash
   # Von Nextcloud-Server:
   curl -I https://mynd.example.com
   ```
4. Wenn localhost: Nutze ngrok/Tunnel für externe URL

---

### **Fehler: "Bot schreibt nicht" oder "Keine Antwort im Chat"**

**Ursache:** Webhook wird nicht vom Nextcloud-Server aufgerufen

**Lösung:**
1. Prüfe Nextcloud-Logs:
   ```bash
   tail -100 /var/www/nextcloud/data/nextcloud.log | grep -i webhook
   ```
2. Prüfe Mynd-Backend-Logs:
   ```bash
   # Im Mynd-Terminal:
   # Suche nach "[talk webhook]" oder "[Talk webhook]"
   ```
3. Stelle sicher, dass der Bot korrekt installiert ist (Schritt 3-5)

---

### **Fehler: "Messages erscheinen als Nutzer, nicht als Bot"**

**Ursache:** Bot API funktioniert nicht, fällt auf User API zurück

**Lösung:**
1. Secret in Mynd Settings erneut überprüfen
2. Backend logs prüfen auf: `via Bot API` vs `via User API`
3. Wenn nur "User API": Secret ist wahrscheinlich falsch
4. Testiere mit korrektem Secret erneut

---

## 📊 Debugging: Logs prüfen

### **Mynd Backend Logs**

```bash
# Im Terminal wo Mynd läuft, nach "talk" filtern:
# Solltest sehen:
# ✅ Talk webhook verified via Nextcloud bot signature
# ✅ Sent Talk message via Bot API to token
# ✅ Talk reply posted successfully
```

### **Nextcloud Logs**

```bash
# SSH zu Nextcloud-Server
tail -f /var/www/nextcloud/data/nextcloud.log | grep -i talk

# Sollte sehen:
# talk:bot:install successful
# talk:bot:setup successful
# Bot API request
```

---

## 🔧 Fortgeschrittene Config

### **Bot-Secret ändern**

Wenn du das Secret ändern möchtest:

```bash
# 1. Alte Bot-Installation löschen
sudo -u www-data php /var/www/nextcloud/occ talk:bot:delete <BOT_ID>

# 2. Neues Secret generieren
openssl rand -hex 24

# 3. Neu installieren mit neuem Secret (Schritt 3)
```

### **Bot aus mehreren Räumen entfernen**

```bash
# Alle Bot-Setup entfernen
sudo -u www-data php /var/www/nextcloud/occ talk:bot:remove-setup <BOT_ID>

# Dann erneut registrieren für neue Räume (Schritt 5)
```

---

## 📞 Support

Falls du Probleme hast:

1. **Prüfe Logs** (siehe Debugging oben)
2. **Vergleiche Secrets** zwischen OCC und Mynd Settings (exakt gleich?)
3. **Teste Webhook-URL** von Nextcloud-Server aus
4. **Prüfe Firewall** - Block port 443?
5. **Stelle sicher Bot ist registriert**: `occ talk:bot:list`

---

## ✅ Checkliste

- [ ] Webhook-URL ist öffentlich erreichbar (kein localhost)
- [ ] Secret wurde mit `openssl rand -hex 24` generiert
- [ ] Bot wurde mit `occ talk:bot:install` installiert
- [ ] Bot-ID wurde gespeichert
- [ ] Bot wurde mit `occ talk:bot:setup` zum Raum hinzugefügt
- [ ] Secret in Mynd Settings gespeichert (exakt gleich wie OCC)
- [ ] Webhook-Test in Mynd erfolgreich (✅ "Bot ist aktiv")
- [ ] Test-Nachricht im Nextcloud Talk versendet
- [ ] Bot antwortet mit Identität "Mynd Bot"

---

## 📖 Weitere Infos

- [Nextcloud Talk Bot API Dokumentation](https://nextcloud-talk.readthedocs.io/en/latest/bot-api/)
- [Activity Streams 2.0 Spec](https://www.w3.org/TR/activitystreams-core/)
- [Mynd Dokumentation](../docs/)
