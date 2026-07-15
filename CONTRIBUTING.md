# Contributing

Thanks for your interest in MYND!

## Development setup

Requirements: Python 3.12+, Node.js 22+, npm 10+, and [uv](https://docs.astral.sh/uv/).

```bash
make setup
make dev
```

## Code Style

- **Python**: Follow PEP 8. Type hints are appreciated.
- **JavaScript/React**: Use the existing patterns — functional components, hooks, CSS modules.
- **CSS**: Use the global design tokens (`var(--brand)`, `var(--ink)`, etc.) defined in `globals.css`.

## Pull Requests

1. Fork the repo and create a feature branch from `main`.
2. Run `make check` locally before pushing.
3. Keep changes focused — one feature or fix per PR.

`make check` runs backend tests, Ruff, the frontend dependency audit, ESLint, and the production frontend build. Browser integration tests are excluded by the default pytest configuration and should be run explicitly when browser code changes.

## Commit Messages

Use conventional commits:

```
feat: add CalDAV event creation
fix: handle empty search results
refactor: extract voice hook from page.js
security: validate file upload paths
```

## Reporting Issues

Include:

- Steps to reproduce
- Expected vs actual behavior
- Browser & OS
- Backend logs (if applicable)

Do not report vulnerabilities in a public issue. Follow [SECURITY.md](SECURITY.md) instead.
