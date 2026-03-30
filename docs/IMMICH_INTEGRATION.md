# Immich Integration Documentation

## Übersicht

Die umfassende Immich-Integration ermöglicht es der KI, auf Fotos aus deiner Immich-Bibliothek zuzugreifen und sie intelligent zu durchsuchen. Die KI kann nach Personen (die Immich bereits kategorisiert hat), Objekten, Daten und Beschreibungen suchen und die gewünschten Bilder mit Vorschaubildern als Miniatur-Karten anzeigen.

## Features

### 1. Intelligente Foto-Suche
- **CLIP-basierte Smart Search**: Nutzt Immichs KI-gestützte Suche für semantisches Verständnis
- **Personensuche**: Suche nach Fotos bestimmter Personen nach Namen
- **Objekterkennung**: Suche nach Objekten in Fotos
- **Datumsfilterung**: Suche nach Fotos aus bestimmten Zeiträumen
- **Standortsuche**: Finde Fotos basierend auf EXIF-Standortdaten

### 2. Miniatur-Karten Anzeige
- Automatische Generierung von Thumbnail-URLs
- Vorschaubilder in optimaler Größe
- Klickbare Karten zum Öffnen der Vollansicht
- Metadaten-Anzeige (Personen, Datum, Standort)

### 3. Nahtlose KI-Integration
- Automatische Erkennung von Foto-Anfragen
- Intelligente Query-Routing
- Multi-Source-Kontext (Fotos + Dateien + Kalender + Tasks)
- Natürlichsprachige Abfragen

## Architektur

### Backend-Komponenten

#### ImmichClient (`backend/features/integration/immich_client.py`)
Hauptklasse für die Kommunikation mit dem Immich-Server:

```python
class ImmichClient:
    def __init__(self, url: str, api_key: str)
    def test_connection() -> bool
    def search_photos_intelligent(query: str, limit: int) -> Dict
    def search_by_person_name(person_name: str, limit: int) -> List
    def get_people() -> List
    def get_all_assets(limit: int, skip: int) -> List
```

**Wichtige Methoden:**
- `search_photos_intelligent()`: Kombiniert verschiedene Suchstrategien (Smart Search + Personensuche)
- `search_smart()`: CLIP-basierte semantische Suche
- `search_by_person_name()`: Sucht Fotos nach Personennamen
- `format_asset_for_display()`: Formatiert Assets für die Frontend-Anzeige

#### API Endpoints (`backend/core/app.py`)

##### `/api/immich/search` (POST)
Sucht Fotos in Immich.

**Request:**
```json
{
  "username": "user123",
  "query": "Fotos vom Urlaub am Meer",
  "limit": 20
}
```

**Response:**
```json
{
  "success": true,
  "query": "Fotos vom Urlaub am Meer",
  "count": 12,
  "results": [
    {
      "id": "asset-id-123",
      "original_file_name": "IMG_2023.jpg",
      "type": "IMAGE",
      "thumbnail_url": "https://immich.example.com/api/asset/thumbnail/asset-id-123?size=preview",
      "asset_url": "https://immich.example.com/api/asset/file/asset-id-123",
      "created_at": "2023-08-15T14:30:00Z",
      "location": "Mallorca, Spanien",
      "people": ["Anna", "Max"],
      "objects": ["beach", "ocean"],
      "tags": ["vacation", "summer"]
    }
  ]
}
```

##### `/api/immich/people` (GET)
Holt alle erkannten Personen.

**Request:**
```
GET /api/immich/people?username=user123
```

**Response:**
```json
{
  "success": true,
  "people": [
    {
      "id": "person-id-1",
      "name": "Anna",
      "thumbnail_path": "/path/to/thumbnail.jpg"
    }
  ]
}
```

##### `/api/immich/assets` (GET)
Holt Assets von Immich.

**Request:**
```
GET /api/immich/assets?username=user123&limit=100&skip=0
```

##### `/api/immich/test` (POST)
Testet die Verbindung zu Immich.

**Request:**
```json
{
  "username": "user123"
}
```

##### `/api/agent/query` (POST)
**Unified Query Endpoint** - Intelligenter Einstiegspunkt für alle Anfragen.

**Request:**
```json
{
  "prompt": "Zeig mir Fotos von Anna vom letzten Urlaub",
  "username": "user123",
  "language": "de",
  "preferred_source": "auto"
}
```

**Supported `preferred_source` values:**
- `"auto"` - Automatische Erkennung (Standard)
- `"photos"` - Nur Fotos durchsuchen
- `"files"` - Nur Dateien durchsuchen

**Response:**
```json
{
  "success": true,
  "response": "Hier sind die Fotos von Anna vom letzten Urlaub:\n\n- [IMG_2023.jpg](https://immich.../file/123)\n  [![IMG_2023.jpg](https://immich.../thumbnail/123)](https://immich.../file/123)\n- [IMG_2024.jpg](https://immich.../file/124)\n  ...",
  "context_used": true,
  "context_count": 3,
  "intent": "photos",
  "sources_used": {
    "photos": true,
    "files": false,
    "calendar": false,
    "todos": false
  }
}
```

### Intent Detection

Die KI erkennt automatisch die Intention der Anfrage:

**Photo Intent:**
- Keywords: `foto`, `fotos`, `bild`, `bilder`, `photo`, `photos`, `person`, `immich`
- Beispiele: "Zeig mir Fotos von Max", "Bilder vom Urlaub"

**File Intent:**
- Keywords: `datei`, `dokument`, `pdf`, `nextcloud`
- Beispiele: "Suche PDF über Steuern", "Dokumente zu Projekt X"

**Mixed Intent:**
- Wenn keine klare Präferenz erkennbar ist
- Durchsucht alle verfügbaren Quellen

### Konfiguration

#### Benutzerspezifische Konfiguration

Jeder Benutzer kann seine eigenen Immich-Credentials hinterlegen:

**Konfigurationsdatei:** `backend/config/user_{username}.json`

```json
{
  "immich_url": "https://immich.example.com",
  "immich_api_key": "YOUR-API-KEY"
}
```

#### Globale Standardkonfiguration

Für alle Benutzer ohne eigene Konfiguration:

**Konfigurationsdatei:** `backend/config/ai_config.json`

```json
{
  "provider": "ollama",
  "base_url": "http://127.0.0.1:11434",
  "model": "gemma3:latest",
  "immich_url_default": "https://immich.example.com",
  "immich_api_key_default": "DEFAULT-API-KEY",
  "vector_db_enabled": true,
  "vector_db_provider": "qdrant",
  "vector_db_path": "./qdrant_data"
}
```

### Konfigurationsfunktionen

```python
def load_user_config(username: str) -> dict
def save_user_config(username: str, config: dict) -> None
def get_immich_client(username: str = None) -> Optional[ImmichClient]
```

## Frontend-Integration

Die Frontend-UI ist in Next.js integriert, insbesondere in `frontend/app/settings/page.js`.

### Konfigurations-Felder
- `immichUrlDefault` - Immich URL Eingabefeld
- `immichApiKeyDefault` - Immich API Key Eingabefeld
- `saveImmichConfig()` - Speichert globale Immich-Defaults
- `testImmichConnection()` - Testet die Verbindung über `/api/immich/test`

### Smart Cards
Die Frontend-UI enthält bereits CSS für:
- `.smart-cards.photo-row` - Horizontale Foto-Galerie
- `.smart-card-thumb` - Thumbnail-Anzeige
- Automatische Erkennung von Foto-Links

### Verwendung im Frontend

Konfiguration erfolgt im Webinterface unter `/settings` im Abschnitt "Immich Integration".
// Oder über natürliche Sprache via Agent Query
await fetch('/api/agent/query', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    prompt: 'Zeig mir Fotos von Anna',
    username: getCurrentUser(),
    language: 'de',
    preferred_source: 'auto'
  })
});
```

## Verwendungsbeispiele

### Beispiel 1: Personensuche
**Anfrage:** "Zeig mir Fotos von Max"

**Ablauf:**
1. Intent Detection erkennt `photos`
2. ImmichClient.search_photos_intelligent() wird aufgerufen
3. Erkennt "Max" als Personenname
4. Sucht alle Personen mit Namen "Max"
5. Holt Fotos dieser Person
6. Formatiert Ergebnisse mit Thumbnails
7. KI generiert natürlichsprachige Antwort mit Markdown-Links

**Antwort:**
```
Hier sind 8 Fotos von Max:

- [IMG_2023.jpg](https://immich.../file/123) - Personen: Max, Anna - Datum: 2023-08-15
  [![IMG_2023.jpg](https://immich.../thumbnail/123)](https://immich.../file/123)
- [IMG_2024.jpg](https://immich.../file/124) - Personen: Max - Ort: Berlin, Deutschland
  [![IMG_2024.jpg](https://immich.../thumbnail/124)](https://immich.../file/124)
```

### Beispiel 2: Thematische Suche
**Anfrage:** "Fotos vom Strandurlaub"

**Ablauf:**
1. CLIP-basierte Smart Search findet semantisch passende Fotos
2. Sucht nach Objekten: "beach", "ocean", "sand"
3. Kombiniert Ergebnisse
4. Formatiert mit Metadaten

### Beispiel 3: Kombinierte Suche
**Anfrage:** "Was hab ich gestern gemacht? Zeig mir auch Fotos"

**Ablauf:**
1. Intent Detection erkennt `mixed`
2. Durchsucht Kalender (gestrige Termine)
3. Durchsucht Fotos (von gestern)
4. Durchsucht Tasks (abgeschlossene Tasks)
5. Kombiniert alle Ergebnisse
6. KI generiert zusammenfassende Antwort

## API Key Generierung (Immich)

1. In Immich einloggen
2. Gehe zu **Benutzereinstellungen** → **API Keys**
3. Klicke auf **Neuen API Key erstellen**
4. Gib dem Key einen Namen (z.B. "MyND AI Assistant")
5. Kopiere den generierten Key (wird nur einmal angezeigt!)
6. Trage Key in MyND-Konfiguration ein

## Sicherheit

- API Keys werden **niemals** im Frontend gespeichert
- Benutzerkonfigurationen liegen in `backend/config/` (nicht öffentlich)
- Keine externen API-Aufrufe ohne explizite Konfiguration
- HTTPS empfohlen für Immich-Verbindungen

## Troubleshooting

### Problem: "Immich nicht konfiguriert"
**Lösung:**
1. Prüfe, ob Immich URL und API Key gesetzt sind
2. Teste Verbindung über `/api/immich/test`
3. Prüfe Logs: `grep -i immich backend/logs/*.log`

### Problem: "Connection timeout"
**Lösung:**
1. Prüfe Immich Server-Erreichbarkeit
2. Prüfe Firewall-Einstellungen
3. Verlängere Timeout in `immich_client.py` falls nötig

### Problem: "Smart Search nicht verfügbar"
**Lösung:**
1. Immich muss CLIP-Modell aktiviert haben
2. Fallback auf Metadata-Search erfolgt automatisch
3. Prüfe Immich-Version (Smart Search ab v1.80+)

### Problem: Keine Personen gefunden
**Lösung:**
1. Prüfe ob Gesichtserkennung in Immich aktiviert ist
2. Warte auf Verarbeitung aller Fotos
3. Überprüfe Personennamen in Immich

## Zukünftige Erweiterungen

### Geplant (Optional)
- **Photo Indexing**: Lokales Caching von Foto-Metadaten
- **Database Schema**: Dedizierte Tabelle für Immich-Assets
- **Batch Import**: Massenimport von Foto-Metadaten
- **Advanced Filters**: Filterung nach Kameramodell, ISO, Belichtung
- **Album Support**: Integration von Immich-Alben
- **Shared Albums**: Zugriff auf geteilte Alben

### Datenbank-Schema (Vorbereitet für zukünftige Version)

```sql
CREATE TABLE immich_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    original_file_name TEXT,
    file_type TEXT,
    created_at REAL,
    location_city TEXT,
    location_country TEXT,
    people JSON,
    objects JSON,
    tags JSON,
    exif_data JSON,
    last_sync REAL NOT NULL,
    FOREIGN KEY (username) REFERENCES users(username)
);

CREATE INDEX idx_immich_photos_username ON immich_photos(username);
CREATE INDEX idx_immich_photos_created_at ON immich_photos(created_at);
CREATE INDEX idx_immich_photos_location ON immich_photos(location_city, location_country);
```

## Zusammenfassung

Die Immich-Integration ist **vollständig funktionsfähig** und ermöglicht:

✅ Intelligente Foto-Suche (CLIP-basiert)
✅ Personensuche nach Namen
✅ Automatische Intent-Erkennung
✅ Multi-Source-Integration (Fotos + Dateien + Kalender + Tasks)
✅ Thumbnail-Generierung für Vorschaukarten
✅ Natürlichsprachige Abfragen
✅ Benutzerspezifische Konfiguration
✅ Frontend-Integration vorbereitet

Die Integration ist **produktionsbereit** und kann sofort verwendet werden!
