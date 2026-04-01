# Benutzerhandbuch: Autonomer KI-Assistent

## Was ist neu?

Dein MYND KI-Assistent ist jetzt **vollständig autonom** und kann selbstständig recherchieren! 🎉

### Früher (Reaktiv)
- Du: "Zeig mir Infos zu Projekt X"
- KI: Sucht nur in einer Quelle → unvollständige Antwort

### Jetzt (Autonom & Proaktiv)
- Du: "Zeig mir Infos zu Projekt X"
- KI:
  1. ✓ Durchsucht automatisch die Wissensdatenbank
  2. ✓ Sucht in allen Nextcloud-Dateien
  3. ✓ Prüft Kalender-Einträge
  4. ✓ Findet zugehörige Kontakte
  5. ✓ Sucht relevante Fotos
  6. ✓ Kombiniert alles zu einer umfassenden Antwort

## Wie funktioniert es?

Der KI-Assistent versteht deine Anfrage und plant automatisch, welche Informationsquellen relevant sind. **Du musst nichts extra tun** - stelle einfach deine Frage!

### Beispiele

#### 1. Umfassendes Thema
**Frage:** "Was weißt du über mein Diarium?"

**KI recherchiert automatisch:**
- 📚 Alle indexierten Dokumente mit "Diarium"
- 📁 Nextcloud-Dateien zum Thema
- 📅 Kalender-Einträge (Meetings, Deadlines)
- ✅ Verknüpfte Aufgaben
- 📸 Zugehörige Fotos/Screenshots

**Ergebnis:** Vollständiger Überblick mit allen relevanten Informationen aus allen Quellen

#### 2. Person suchen
**Frage:** "Wer ist Max Mustermann und wann haben wir zuletzt kommuniziert?"

**KI recherchiert automatisch:**
- 👤 Kontaktdaten aus Adressbuch
- 📧 Erwähnungen in Dokumenten
- 📅 Gemeinsame Kalendereinträge
- 💬 Chat-Verläufe (wenn verfügbar)

**Ergebnis:** Komplettes Profil mit Kontakthistorie

#### 3. Projektinformationen
**Frage:** "Zeige mir alles zu Projekt Alpha"

**KI recherchiert automatisch:**
- 📄 Projektdokumente und Berichte
- 👥 Beteiligte Personen
- 📅 Projekt-Termine und Meilensteine
- ✅ Offene und erledigte Aufgaben
- 📸 Projekt-Fotos und Screenshots

**Ergebnis:** Vollständige Projektübersicht

#### 4. Urlaubsfotos
**Frage:** "Zeig mir Fotos vom Italien-Urlaub"

**KI recherchiert automatisch:**
- 📸 Fotos mit Location "Italien"
- 📁 Reisedokumente (Buchungen, Tickets)
- 📅 Reisezeitraum im Kalender
- 📝 Reisenotizen und Tagebücher

**Ergebnis:** Fotos eingebettet + alle Reiseinfos

## Intelligente Funktionen

### 1. Keyword-Extraktion
Die KI erkennt automatisch wichtige Suchbegriffe in deiner Anfrage:

- **Frage:** "Kannst du mir alle Informationen über das Diarium-Projekt zeigen?"
- **Erkannte Keywords:** "informationen", "diarium", "projekt"
- **Suchbegriff:** "informationen diarium projekt"

### 2. Intent-Erkennung
Die KI erkennt, welche Art von Information du suchst:

| Anfrage-Typ | Beispiele | Ausgeführte Aktionen |
|-------------|-----------|----------------------|
| **Personen** | "Wer ist...", "Kontakt von...", "Email von..." | Kontakte durchsuchen |
| **Zeit/Termine** | "Wann...", "Termin", "Meeting", "Kalendar" | Kalender durchsuchen |
| **Aufgaben** | "Was muss ich...", "Aufgabe", "Todo" | Aufgaben durchsuchen |
| **Fotos** | "Zeig Foto", "Bild von..." | Immich durchsuchen |
| **Dokumente** | "Datei", "Dokument", "PDF" | Nextcloud + Index durchsuchen |

### 3. Parallele Suche
Alle Suchvorgänge laufen **gleichzeitig** ab → schnellere Ergebnisse!

### 4. Intelligente Kombinierung
Die KI kombiniert Informationen aus verschiedenen Quellen zu einer kohärenten Antwort.

## Welche Quellen werden durchsucht?

### Immer durchsucht (wenn relevant):
1. **Wissensdatenbank** (indexierte Dokumente)
   - Alle PDF, DOCX, TXT, MD Dateien
   - Volltext-Suche mit Relevanz-Score

2. **Nextcloud Unified Search**
   - Dateien
   - Kontakte
   - Kalender-Events
   - Aufgaben
   - Talk-Nachrichten
   - Deck-Karten

3. **Immich Fotos**
   - Intelligente Bilderkennung
   - Personen, Orte, Objekte
   - Metadaten (Datum, GPS)

### Bei Bedarf durchsucht:
4. **Kalender** (bei Zeit-Bezug)
5. **Aufgaben** (bei Task-Bezug)
6. **Kontakte** (bei Personen-Bezug)
7. **Wetter** (bei Wetter-Fragen)
8. **Sicherheitswarnungen** (bei Sicherheits-Fragen)
9. **Aktivitäts-Stream** (bei "Was ist neu?")

## Tipps für beste Ergebnisse

### ✅ Gut formulierte Fragen

```
"Zeig mir alle Infos zum Meum Diarium"
→ KI sucht umfassend nach "meum" und "diarium"

"Was weißt du über Projekt Alpha?"
→ KI sucht in allen Quellen nach Projekt-Infos

"Wann treffe ich Max Mustermann?"
→ KI sucht Kalender + Kontakte
```

### ✅ Natürliche Sprache
Sprich mit der KI wie mit einem Menschen:

```
"Ich suche Informationen über mein Diarium-Projekt.
 Kannst du mir sagen, was es gibt?"
```

### ✅ Kontext nutzen
Die KI merkt sich den Gesprächsverlauf:

```
Du: "Zeig mir Projekt Alpha"
KI: [Zeigt Infos]

Du: "Wer arbeitet daran?"
KI: [Versteht, dass es um Projekt Alpha geht]
```

### ❌ Zu vermeiden

```
❌ "Datei"  → Zu unspezifisch
✅ "Finde Dateien über Projekt X"

❌ "Info"  → Zu vage
✅ "Zeige alle Informationen zum Diarium"
```

## Was die KI automatisch macht

### Ohne dass du es explizit sagst:

1. **Mehrere Quellen durchsuchen**
   - Du musst nicht sagen "Suche in Nextcloud UND in der Wissensbasis"
   - Die KI macht das automatisch

2. **Relevante Informationen filtern**
   - Die KI zeigt nur relevante Ergebnisse
   - Unwichtiges wird aussortiert

3. **Informationen verknüpfen**
   - Dokumente ↔ Personen ↔ Termine
   - Die KI erkennt Zusammenhänge

4. **Kontext beachten**
   - Die KI berücksichtigt vorherige Fragen
   - Du musst nicht alles wiederholen

## Beispiel-Dialog

**Du:** "Was weißt du über mein Diarium?"

**KI (im Hintergrund):**
```
[INFO] Starte autonome Recherche...
[INFO] Plane 5 Aktionen
[INFO] ✓ Wissensdatenbank: 12 Dokument-Chunks gefunden
[INFO] ✓ Nextcloud-Dateien: 8 Dateien gefunden
[INFO] ✓ Nextcloud Unified Search: 15 Ergebnisse
[INFO] ✓ Fotos: 3 Screenshots gefunden
[INFO] ✓ Aufgaben: 2 offene Aufgaben gefunden
[INFO] Autonome Recherche erfolgreich abgeschlossen
```

**KI (sichtbare Antwort):**
```
Ich habe umfassende Informationen zu deinem Diarium gefunden:

📚 **Dokumente (12 gefunden):**
Dein Diarium ist ein persönliches Projekt zur Dokumentation...
[Details aus indexierten Dokumenten]

📁 **Dateien (8 gefunden):**
- Projektplan_Diarium_v2.pdf
- Notizen_Diarium_Januar.md
- [weitere Dateien mit Links]

✅ **Offene Aufgaben (2):**
- Kapitel 5 fertigstellen (fällig: morgen)
- Korrekturlesen (fällig: nächste Woche)

📸 **Screenshots (3):**
[Embedded images mit Beschreibungen]

Möchtest du mehr Details zu einem bestimmten Aspekt?
```

## Häufig gestellte Fragen (FAQ)

### Wie weiß die KI, was relevant ist?
Die KI analysiert deine Frage und identifiziert Schlüsselwörter. Basierend darauf plant sie, welche Quellen durchsucht werden sollen.

### Warum findet die KI manchmal nichts?
Mögliche Gründe:
- Die Wissensdatenbank wurde noch nicht indexiert
- Die gesuchten Informationen sind in Nextcloud nicht verfügbar
- Die Suchbegriffe sind zu allgemein

**Lösung:** Stelle spezifischere Fragen mit klaren Suchbegriffen.

### Kann ich die autonome Recherche deaktivieren?
Technisch ja (in der Konfiguration), aber warum? Sie macht die KI viel leistungsfähiger! 😊

### Werden meine Daten sicher behandelt?
Ja! Die KI:
- Hat nur **Lesezugriff** auf deine Daten
- Speichert keine sensiblen Informationen außerhalb deines Systems
- Verwendet deine Nextcloud-Credentials sicher
- Alle Aktionen werden lokal ausgeführt

### Wie lange dauert die autonome Recherche?
Sehr kurz! Alle Suchvorgänge laufen **parallel**, daher meist nur 1-3 Sekunden.

### Was ist der Unterschied zur alten Version?
| Alt | Neu |
|-----|-----|
| Sucht nur in einer Quelle | Durchsucht automatisch alle relevanten Quellen |
| Du musst spezifizieren, wo gesucht wird | KI entscheidet automatisch |
| Oft unvollständige Antworten | Umfassende, quellenübergreifende Antworten |
| Keine Verknüpfungen zwischen Quellen | Intelligente Informationssynthese |

## Systemanforderungen

Für optimale Leistung sollte dein System haben:
- ✅ Nextcloud mit konfigurierten Credentials
- ✅ Indexierte Wissensdatenbank (über UI: Einstellungen → Indexierung)
- ✅ Immich (optional, für Foto-Suche)
- ✅ Ollama mit einem LLM (z.B. Llama 3 oder Mistral)

## Weitere Ressourcen

- **Technische Dokumentation:** `docs/AUTONOMOUS_AGENT.md`
- **API-Integration:** `docs/NEXTCLOUD_API_INTEGRATIONS.md`
- **Indexierung:** Siehe UI-Einstellungen

## Feedback und Support

Probleme oder Verbesserungsvorschläge?
- GitHub Issues: [github.com/SchBenedikt/mynd/issues]
- Logs prüfen: Siehe `backend.log` für Details zur autonomen Recherche

---

**Viel Spaß mit deinem neuen autonomen KI-Assistenten!** 🚀
