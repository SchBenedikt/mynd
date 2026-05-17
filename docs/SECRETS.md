Kurzinfo: Umgang mit Geheimnissen im Repository

- Falls ein Geheimnis kompromittiert wurde: sofort das Secret rotieren (Passwort/App‑Token ändern).
- Dieses Repo enthält jetzt eine `pre-commit`‑Konfiguration zur Erkennung von Secrets. Installiere lokal mit:

```bash
pipx install pre-commit || pip install --user pre-commit
pre-commit install
```

- Nach History‑Rewrite: alle Mitwirkenden müssen ihre lokalen Klone neu klonen (`git clone`) oder lokale Branches neu setzen.
- Wenn du noch die Historie komplett säubern willst (falls das Secret bereits öffentlich war), benutze das Mirror+`git-filter-repo` oder BFG, wir haben das bereits ausgeführt.

Kontakt: Repository‑Admin für weitere Fragen.
