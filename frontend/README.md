# Frontend (Next.js)

Next.js-basiertes Frontend für das MYND-Backend.

## Start

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

Frontend: http://localhost:3000
Backend: http://127.0.0.1:5001

## Konfiguration

- API-Ziel wird über `NEXT_PUBLIC_BACKEND_URL` in `.env.local` gesteuert
- Nutzt die Endpunkte `/api/chat`, `/api/ollama/status`, `/api/knowledge/status`, `/api/ai/config` u.a.
- Einstellungen für Immich, Nextcloud, AI unter `/settings`

## Seiten

| Route | Beschreibung |
|-------|-------------|
| `/` | Chat-Interface |
| `/settings` | Einstellungen (AI, Nextcloud, Immich, Kalender) |
| `/setup` | Setup-Wizard |
| `/admin` | Admin-Bereich |
| `/knowledge-graph` | Knowledge-Graph-Visualisierung |
| `/internal` | Interne Debug-Tools |
