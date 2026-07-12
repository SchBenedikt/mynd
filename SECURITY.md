# Security Policy

## Supported versions

Security fixes are applied to the latest revision of the default branch.

## Reporting a vulnerability

Please do not open a public issue for suspected vulnerabilities. Contact the repository
owner privately and include reproduction steps, affected versions, impact, and any known
mitigation. Avoid including real credentials or personal data.

## Deployment guidance

MYND is designed for trusted, local networks. Place internet-facing deployments behind
TLS and a hardened reverse proxy, restrict `CORS_ALLOWED_ORIGINS`, use strong unique
passwords, and enable only integrations that are required. Treat the local `data/`
directory as sensitive because it can contain access tokens and service credentials.
