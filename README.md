# Jev Desk v0.3 — deployment package

Mobile-first managed-cloud shadow research desk.

## Current safety boundary
- Shadow only
- No wallet/private keys
- No FOMO order submission
- Real trading hard-disabled
- Mock discovery remains enabled until verified live-data adapters are connected

## Deployment
Includes Dockerfile, render.yaml, railway.json, /health, and a phone dashboard at `/`.

The cloud host will provide an HTTPS URL. Open it in Safari and use Share → Add to Home Screen.

## Important
Never put API secrets in GitHub source files. Add them as environment variables in the cloud host.

SQLite is currently local to the running container. Before continuous research, attach durable storage or migrate events to a managed database so redeployments cannot erase the research dataset.
