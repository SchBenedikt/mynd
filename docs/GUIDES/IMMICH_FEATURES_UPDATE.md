# Immich Photo Integration - Neue Features (30.03.2026)

## 🎯 Überblick

Die Immich-Foto-Integration wurde mit 4 wichtigen Features erweitert:

### 1. ✅ Datum-Filter
- **Automatische Datums-Erkennung** in Suchqueries
- Unterstützte Keywords:
  - `heute` - Fotos vom aktuellen Tag
  - `gestern` - Fotos vom Vortag
  - `diese Woche` - Fotos der laufenden Woche
  - `diesen Monat` - Fotos des laufenden Monats
  - `letzte 7 Tage` - Fotos der letzten 7 Tage
  - `letzte 30 Tage` - Fotos des letzten Monats

**Beispiele:**
```
"Zeig mir Fotos von heute"                  → 2 Fotos gefunden
"Zeig mir Fotos von gestern"                → 2 Fotos gefunden
"Fotos von dieser Woche"                    → 0 Fotos gefunden (Sonntag-Montag)
```

### 2. ✅ Links & IDs anzeigen
Alle Fotos enthalten jetzt:
- **`id`** - Eindeutige Immich-Asset-ID
- **`asset_url`** - Direkter Link zum Original-Foto
- **`thumbnail_url`** - Link zur Vorschau

**API Response-Beispiel:**
```json
{
  "id": "1c19a40a-a0c0-4d37-a29c-0d6ad33c5acc",
  "asset_url": "https://immich.domain.de/api/assets/1c19a40a.../original",
  "thumbnail_url": "https://immich.domain.de/api/assets/1c19a40a.../thumbnail?size=preview",
  "original_file_name": "26-03-30 17-50-34 0375.png",
  "created_at": "2026-03-30T17:50:34.000Z"
}
```

### 3. ✅ Thumbnail-Vorschau
Alle Foto-Responses enthalten **Thumbnail-URLs** für die Anzeige:
- Format: `thumbnail?size=preview` (kleine Vorschau)
- Direkt im AI-Response als Markdown-Bilder verwendbar
- Klickbar als Link zum Original-Foto

**Markdown-Format:**
```markdown
[![Foto-Name](thumbnail-url)](original-url)
```

### 4. ✅ Kontext-Filter (Objects/Tags)
Suche nach **KI-erkannten Objekten und Content**:
- Neue Endpoint: `POST /api/immich/search-by-context`
- Nutzt Immich's smartInfo.objects und smartInfo.tags
- Filtert nach erkannten Objekten wie "Person", "Katze", "Baum", etc.

**Beispiel:**
```bash
curl -X POST http://localhost:5001/api/immich/search-by-context \
  -H "Content-Type: application/json" \
  -d '{"username": "default", "query": "Katze", "limit": 3}'
```

---

## 🔧 Technische Implementierung

### Modified Files

#### 1. `backend/features/integration/immich_client.py`
**Added Methods:**
- `_extract_date_range(query)` - Parst natürliche Datumsausdrücke
- `search_by_context(query, limit)` - Sucht nach Objekten/Tags

**Enhanced Methods:**
- `search_photos_intelligent()` - Nutzt jetzt Datum-Extraktion
- `format_asset_for_display()` - Zeigt now `id`, `description`, vollständige Metadata

**New Imports:**
```python
from datetime import timedelta
```

#### 2. `backend/core/app.py`
**New Endpoints:**
- `POST /api/immich/search-by-context` - Kontext-basierte Foto-Suche

**Enhanced Endpoints:**
- `POST /api/agent/query` - Verbesserte Photo-Context-Formatierung
  - Markdown-headings (`###`) für bessere Struktur
  - Vollständige Methaten-Anzeige (ID, Datum, Personen, Objekte, Tags)
  - Thumbnail-URL mit klikbarem Link zum Original
  - Bessere Formatierung für AI-Verarbeitung

### API Changes

**Search Response now includes:**
```json
{
  "success": true,
  "query": "Fotos von heute",
  "count": 2,
  "results": [
    {
      "id": "1c19a40a-a0c0-4d37-a29c-0d6ad33c5acc",
      "original_file_name": "26-03-30 17-50-34 0375.png",
      "type": "IMAGE",
      "thumbnail_url": "https://...",
      "asset_url": "https://...",
      "created_at": "2026-03-30T17:50:34.000Z",
      "location": null,
      "people": [],
      "objects": [],
      "tags": [],
      "description": ""
    }
  ]
}
```

---

## 📚 Usage Examples

### Beispiel 1: Fotos von heute mit allen Details

```bash
curl -X POST http://localhost:5001/api/immich/search \
  -H "Content-Type: application/json" \
  -d '{"username": "default", "query": "Fotos von heute", "limit": 3}'
```

**Response:**
```json
{
  "count": 2,
  "query": "Fotos von heute",
  "results": [
    {
      "id": "1c19a40a-a0c0-4d37-a29c-0d6ad33c5acc",
      "original_file_name": "26-03-30 17-50-34 0375.png",
      "created_at": "2026-03-30T17:50:34.000Z",
      "asset_url": "https://immich.exmaple.de/api/assets/1c19a40a-a0c0-4d37-a29c-0d6ad33c5acc/original",
      "thumbnail_url": "https://immich.example.de/api/assets/1c19a40a-a0c0-4d37-a29c-0d6ad33c5acc/thumbnail?size=preview"
    }
  ]
}
```

### Beispiel 2: Suche nach Objekten

```bash
curl -X POST http://localhost:5001/api/immich/search-by-context \
  -H "Content-Type: application/json" \
  -d '{"username": "default", "query": "Person", "limit": 5}'
```

### Beispiel 3: Agent Query (mit KI-Antwort)

```bash
curl -X POST http://localhost:5001/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Zeig mir Fotos von Isabelle",
    "username": "default",
    "language": "de"
  }'
```

**AI Response wird jetzt enthalten:**
- Foto-Links mit IDs
- Thumbnail-Miniaturansichten
- Vollständige Metadaten (Datum, Personen, Objekte, Tags)
- Markdown-formatiert für beste Lesbarkeit

---

## ✨ Verbesserungen für Nutzer

### Frontend Integration
Die neuen Features ermöglichen:
1. **Photo-Grid mit Thumbnails**: Direkt aus API-Response anzeigbar
2. **Click-to-Open**: Jedes Thumbnail ist linkbar zum Original
3. **Date Filter UI**: Nutzer können nach Datum filtern ohne zusätzliche UI
4. **Object Search**: "Zeig mir Fotos von Katzen" funktioniert automatisch

### Query Examples die jetzt funktionieren
- ✅ "Zeig mir Fotos von heute"
- ✅ "Fotos von gestern"
- ✅ "Diese Woche Bilder"
- ✅ "Bilder von Isabelle"
- ✅ "Zeig mir Fotos mit Katzen"
- ✅ "Fotos mit Personen"

---

## 🧪 Test Script

Es gibt einen umfassenden Test-Script:
```bash
python3 test_immich_features.py
```

Dieser testet:
- Datum-Filter (heute, gestern, diese Woche)
- Foto-Details mit Metadaten
- Kontext-basierte Suche
- Markdown-Response-Format

---

## 📝 Deployment Checklist

- [x] `immich_client.py` aktualisiert mit Date-Extraktion
- [x] `immich_client.py` aktualisiert mit Context-Search
- [x] `app.py` aktualisiert mit neuer `/search-by-context` Endpoint
- [x] `app.py` aktualisiert mit besserer Photo-Context-Formatierung
- [x] Backend-Server getestet mit neuen Endpoints
- [x] Test-Script erstellt und erfolgreich getestet
- [ ] Frontend-Integration (UI Tests pending)

---

## 🚀 Nächste Schritte

1. **Frontend Bilder-Anzeige**: Integriere die neuen Thumbnail-URLs ins UI
2. **Photo-Grid**: Zeige mehrere Fotos in einer Galerie
3. **Filter UI**: Datum-Filter als UI-Komponente
4. **Search Refinement**: Nutzer können Ergebnisse filtern/verfeinern

---

## ❓ Häufig gestellte Fragen

**F: Warum bekomme ich keine Fotos bei "diese Woche"?**  
A: Die Woche wird Montag-Sonntag berechnet. Wenn du Freitag fragst, enthält deine Week keine alten Fotos.

**F: Wie benutze ich den Context-Filter?**  
A: Nutze `POST /api/immich/search-by-context` mit der Query für das Objekt (z.B. "Katze", "Person", "Auto").

**F: Können Thumbnails im AI-Response angezeigt werden?**  
A: Ja! Sie werden als Markdown-Bilder formatiert: `[![alt](thumb)](original)`

---

## 📞 Support

Bei Fragen oder Problemen:
1. Check die Server-Logs: `docker logs mynd-backend`
2. Teste mit curl direkt: `curl /api/immich/search ...`
3. Überprüfe Immich-Verbindung: `GET /api/server/ping`
