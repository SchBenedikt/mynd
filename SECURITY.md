# Security Policy

## Supported versions

Security fixes are applied to the latest revision of the default branch.

## Reporting a vulnerability

Please do not open a public issue for suspected vulnerabilities. Use GitHub's private
vulnerability reporting for this repository when available, or contact the repository
owner privately. Include reproduction steps, affected versions, impact, and any known
mitigation. Never include real credentials or personal data in a public report.

## Deployment guidance

MYND is designed for trusted, local networks. Place internet-facing deployments behind
TLS and a hardened reverse proxy, restrict `CORS_ALLOWED_ORIGINS`, use strong unique
passwords, and enable only integrations that are required. Treat the local `data/`
directory as sensitive because it can contain access tokens and service credentials.

Agent tools can execute commands, run Python, access configured services, and write files.
Keep the permission mode restrictive, set `MYND_WORKSPACE_DIR`, and only allow private HTTP
targets through `MYND_HTTP_ALLOW_PRIVATE_HOSTS` when they are explicitly trusted. Rotate a
credential immediately if it is ever committed or exposed in logs.
