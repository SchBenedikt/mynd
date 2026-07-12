# Contributing

Thank you for improving MYND.

1. Create a focused branch from the current default branch.
2. Keep credentials, generated files, and local runtime state out of commits.
3. Add or update tests for behavior changes.
4. Run `make check` before opening a pull request.
5. Explain the problem, solution, verification, and any migration impact in the pull request.

Python code should pass Ruff and use explicit exception handling around network and file
boundaries. Frontend changes should keep the production build and ESLint checks green.
Security-sensitive changes should include regression tests and avoid exposing internal
errors or secrets in API responses.
