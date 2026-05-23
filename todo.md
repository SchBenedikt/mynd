### ToDo
### ToDo (priorität: Sicherheit zuerst)

- [ ] Sicherheits-Maßnahmen
	- [ ] Setze `AUTH_COOKIE_SECURE=true` in Produktion und erzwinge HTTPS
	- [ ] Verschlüssele persistente Tokens (Nextcloud) mit einem Umgebungs-geheimnis
	- [ ] Nutze bcrypt / passlib (erledigt)
	- [ ] Admin-UI zum sicheren Verwalten von Nutzern (siehe /admin)

- [ ] Admin & Betrieb
	- [ ] Admin-UI zum Anlegen/Zurücksetzen von Benutzern
	- [ ] Automatischer Refresh gespeicherter Nextcloud-Tokens (Background-Job)

- [ ] Funktionalität / Features
	- [ ] Zeige passende Quellen in der Next.js Anwendung
	- [ ] Füge Quellen in die Antwort ein
	- [ ] Verbessere das Training, erweitere das und überarbeite das
	- [ ] Füge externe API-Integrationen von Nextcloud hinzu (Carddav, Search API, Notifications API)

- [ ] UX
	- [ ] Die KI sollte auch z.B Termine/Dateien erstellen können. Hierbei sollte es ein interaktives Formular geben, dass man bei Nachfragen ausfüllen muss.