# Frontend (Next.js)

Dieses Frontend uebernimmt das Design aus `ui.html` und bindet dein bestehendes Flask-Backend an.

## Start

1. Abhaengigkeiten installieren:

   npm install

2. Environment-Datei anlegen:

   cp .env.local.example .env.local

3. Frontend starten:

   npm run dev

Frontend: http://localhost:3000
Backend (Flask): http://127.0.0.1:5001

## Hinweise

- API-Ziel wird ueber `NEXT_PUBLIC_BACKEND_URL` gesteuert.
- Das UI nutzt `/api/chat`, `/api/ollama/status` und `/api/knowledge/status`.
- `ui.html` bleibt als Referenz erhalten.
