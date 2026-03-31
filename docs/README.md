# Lokale AI Chat Anwendung mit Nextcloud-Integration

Eine lokale Chat-Anwendung, die mit Ollama läuft und personalisierte Antworten basierend auf Dokumenten aus Nextcloud oder lokalen Verzeichnissen gibt.

## Features

- 🤖 Integration mit Ollama für lokale AI-Modelle
- 📚 RAG-System (Retrieval-Augmented Generation) für personalisierte Antworten
- ☁️ Nextcloud-Integration über WebDAV
- 📁 Lokale Dokumenten-Verarbeitung
- 📄 Multi-Format Parser: PDF, Word, Excel, PowerPoint, Markdown, Text, HTML
- 🎨 Moderne Web-UI mit Chat-Interface
- ⚡ Einfache Textsuche für Kontext-Einbindung
- 🔄 Automatische Dokumenten-Indexierung

## Unterstützte Dateiformate

- **PDF**: `.pdf`
- **Microsoft Word**: `.docx`, `.doc`
- **Microsoft Excel**: `.xlsx`, `.xls`
- **Microsoft PowerPoint**: `.pptx`, `.ppt`
- **Markdown**: `.md`, `.markdown`
- **Text**: `.txt`
- **HTML**: `.html`, `.htm`

## Voraussetzungen

1. **Ollama installiert und läuft**
   ```bash
   # Ollama installieren
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Ollama starten
   ollama serve
   
   # Modell herunterladen (z.B. gemma3)
   ollama pull gemma3
   ```

2. **Python 3.8+**

3. **Optional: Nextcloud-Server** mit WebDAV-Zugriff

## Installation

1. Repository klonen oder Projekt erstellen
2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

## Konfiguration

Die Konfiguration erfolgt über die `.env` Datei:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:latest

# Optional für Nextcloud
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_USERNAME=your-username
NEXTCLOUD_PASSWORD=your-password
```

## Anwendung starten

```bash
python app.py
```

Die Anwendung ist dann unter `http://localhost:5001` erreichbar.

## Nutzung

### 1. Wissensbasis konfigurieren

**Option A: Nextcloud-Dokumente**
1. Im Web-Interface den "Nextcloud" Tab auswählen
2. Nextcloud-URL, Benutzername und Passwort eingeben
3. Optional ein spezifisches Verzeichnis angeben
4. Auf "Nextcloud-Dokumente laden" klicken

**Option B: Lokale Dokumente**
1. Im Web-Interface den "Lokal" Tab auswählen
2. Pfad zum lokalen Verzeichnis eingeben
3. Auf "Lokale Dokumente laden" klicken

### 2. Chatten

Nachdem die Wissensbasis geladen wurde, können Fragen zu den Inhalten der Dokumente gestellt werden. Das System sucht automatisch nach relevanten Informationen und integriert sie in die Antworten.

## API Endpunkte

- `GET /` - Chat-Interface
- `POST /api/agent/query` - Chat-Anfrage senden
- `POST /api/knowledge/load-nextcloud` - Wissensbasis von Nextcloud laden
- `POST /api/knowledge/load-local` - Wissensbasis aus lokalem Verzeichnis laden
- `GET /api/knowledge/sources` - Informationen über geladene Quellen
- `GET /api/knowledge/status` - Status der Wissensbasis
- `GET /api/ollama/status` - Ollama-Verbindungsstatus

## Funktionsweise

1. **Dokumenten-Verarbeitung**: Die unterstützten Dateiformate werden analysiert und in reinen Text umgewandelt
2. **Text-Chunking**: Lange Dokumente werden in kleinere, verdaubare Stücke aufgeteilt
3. **Kontext-Suche**: Bei jeder Anfrage werden relevante Text-Chunks mittels Keyword-Matching gefunden
4. **Kontext-Einbindung**: Die gefundenen Chunks werden als Kontext an das AI-Modell übergeben
5. **Personalisierung**: Das AI-Modell generiert Antworten basierend auf dem persönlichen Kontext

## Nextcloud-Integration

Die Anwendung nutzt WebDAV für den Zugriff auf Nextcloud:

- **Sicherer Zugriff**: HTTPS-Unterstützung
- **Verzeichnis-Browsing**: Rekursives Durchsuchen von Verzeichnissen
- **Datei-Filter**: Automatische Filterung nach unterstützten Formaten
- **Fehlerbehandlung**: Robuste Fehlerbehandlung bei Verbindungsproblemen

## Sicherheitshinweise

- **Passwörter**: Passwörter werden nur für die Sitzung im Speicher gehalten
- **HTTPS**: Bei Nextcloud-Verbindungen sollte HTTPS verwendet werden
- **Lokaler Modus**: Die Anwendung läuft standardmäßig lokal und sendet keine Daten an externe Dienste (außer Ollama)

## Troubleshooting

### Ollama Verbindung fehlgeschlagen
- Stelle sicher, dass Ollama läuft (`ollama serve`)
- Überprüfe den Port (Standard: 11434)
- Kontrolliere, ob das Modell heruntergeladen wurde

### Nextcloud-Verbindungsprobleme
- Überprüfe URL und Zugangsdaten
- Stelle sicher, dass WebDAV aktiviert ist
- Prüfe Firewall-Einstellungen

### Dokumenten-Verarbeitungsfehler
- Überprüfe, ob die Dateien nicht korrupt sind
- Stelle sicher, dass die Dateiformate unterstützt werden
- Prüfe die Berechtigungen bei lokalen Dateien

### Performance-Probleme
- Reduziere die Anzahl der Dokumente
- Passe die Chunk-Größe im Code an
- Nutze ein kleineres AI-Modell

## Technologie-Stack

- **Backend**: Flask (Python)
- **AI-Modell**: Ollama mit Gemma3
- **Dokumenten-Parser**: PyPDF2, python-docx, openpyxl, python-pptx
- **Nextcloud-Client**: webdavclient3
- **Frontend**: HTML5, CSS3, JavaScript
- **Styling**: Modern CSS mit Gradienten

## Erweiterungsmöglichkeiten

- Unterstützung für weitere Dateiformate
- Vektor-Suche mit Embeddings für bessere Relevanz
- Chat-Historie-Speicherung
- Benutzer-Authentifizierung
- Plugin-System für verschiedene Datenquellen
- Batch-Verarbeitung großer Dokumentensammlungen
