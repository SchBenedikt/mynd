# Contributing

Thanks for your interest in MYND!

## Code Style

- **Python**: Follow PEP 8. Type hints are appreciated.
- **JavaScript/React**: Use the existing patterns — functional components, hooks, CSS modules.
- **CSS**: Use the global design tokens (`var(--brand)`, `var(--ink)`, etc.) defined in `globals.css`.

## Pull Requests

1. Fork the repo and create a feature branch from `main`.
2. Run `make check` locally before pushing.
3. Keep changes focused — one feature or fix per PR.

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
