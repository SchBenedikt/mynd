# MYND frontend

The MYND web application is built with Next.js 16 and React 19.

## Run locally

From the repository root:

```bash
npm install
npm run dev
```

The frontend opens at `http://localhost:3000` and connects to the backend at `http://127.0.0.1:5001`. Users can override the backend URL from the login page; the value is stored locally in the browser.

## Main routes

| Route | Purpose |
|---|---|
| `/` | Chat workspace |
| `/login` | Authentication and registration |
| `/language` | Language selection |
| `/setup` | First-run setup wizard |
| `/settings` | Models, integrations, indexing, users, and appearance |
| `/projects` | Project organization |
| `/knowledge-graph` | Knowledge graph visualization |

Run `npm run lint` and `npm run build` before submitting frontend changes.
