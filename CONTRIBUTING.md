# Contributing to MYND

Thank you for contributing to MYND! This document provides guidelines for participating in the project.

## Branch Strategy

- `main` - Production-ready code
- `develop` - Development branch
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches
- `claude/*` - AI-assisted development branches

## Development Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Before Submitting PR

1. **Run Tests**
   ```bash
   cd tests
   python -m pytest . -v
   ```

2. **Code Quality**
   - Follow Python PEP 8
   - Use meaningful variable names
   - Add docstrings to functions
   - Keep methods focused and small

3. **Security**
   - Validate all inputs
   - Don't commit secrets
   - Use security utilities provided
   - Check OWASP Top 10 implications

4. **Documentation**
   - Update docs/ if behavior changes
   - Add docstrings and type hints
   - Include usage examples

## File Organization

```
scripts/
  ├── demo/          → Demo scripts
  ├── debug/         → Debug & testing
  ├── examples/      → Usage examples
  └── inspect/       → Inspection tools

data/
  ├── cache/         → Database files
  ├── training/      → Training data
  └── config/        → Configuration

tests/               → All test files
docs/                → All documentation
reports/             → Generated reports
```

## Testing Requirements

### Unit Tests
- Test single functions in isolation
- Use meaningful test names
- Test positive and negative cases

### Security Tests
- Test injection attempts
- Validate input handling
- Check authentication/authorization

### Edge Cases
- Boundary conditions
- Null/undefined handling
- Error scenarios

## Commit Messages

```
[TYPE] Brief description

Optional detailed explanation
- Bullet point details
- Follow your changes

Fixes: #123
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `security`

## PR Review Checklist

- [ ] Tests added/updated
- [ ] Docs updated
- [ ] No hardcoded secrets
- [ ] Security implications considered
- [ ] Code formatted properly
- [ ] Breaking changes documented

## Architecture Decisions

- Backend uses Flask/FastAPI
- Frontend uses Next.js
- Database TBD per config
- Authentication providers supported

## Questions?

- Check existing documentation in `/docs`
- Review security guidelines in `/docs/SECURITY`
- Check code review report in `/reports`

Thank you for contributing! 🙏
