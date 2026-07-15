# MYND frontend

The MYND web application is built with Next.js 16 and React 19.

## Run locally

From the repository root:

```bash
npm ci --prefix frontend
npm run dev --prefix frontend
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

From the repository root, run `npm run lint --prefix frontend` and `npm run build --prefix frontend` before submitting frontend changes. The lint command currently reports warnings without failing; new changes should not add warnings.
