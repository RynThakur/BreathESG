# Breathe ESG — Data Ingestion & Review Prototype

A Django REST + React application for ingesting, normalizing, and reviewing emissions data from three enterprise source types.

**Live demo**: [add Railway URL here after deployment]  
**Login**: `analyst` / `demo1234`

---

## What it does

Ingests emissions data from:
1. **SAP flat file (CSV)** — fuel and procurement data from SAP MM/FI module exports
2. **Utility portal CSV** — electricity data in Green Button / EnergyCAP format
3. **Corporate travel JSON** — Concur-style expense report exports with AIRFR, HOTEL, TAXI entries

Normalizes all quantities to canonical units (kWh, litres, km, kg, USD), classifies records by GHG Protocol scope (1/2/3), flags anomalies, and surfaces a review dashboard where analysts can approve, flag, or reject records before they're locked for audit.

---

## Deployment (Railway)

### Backend

1. Create a new Railway project → "New Service" → "GitHub Repo" → select this repo
2. Set root directory to `backend/`
3. Add a PostgreSQL database plugin to the project
4. Set environment variables:
   ```
   SECRET_KEY=<generate a random 50-char string>
   DEBUG=False
   ALLOWED_HOSTS=<your-backend-url>.railway.app
   CORS_ALLOWED_ORIGINS=https://<your-frontend-url>.railway.app
   DATABASE_URL=<auto-set by Railway PostgreSQL plugin>
   ```
5. Railway will run `Procfile` automatically: migrates, seeds demo data, starts gunicorn

### Frontend

1. "New Service" → "GitHub Repo" → same repo, root directory `frontend/`
2. Set environment variable:
   ```
   VITE_API_URL=https://<your-backend-url>.railway.app
   ```
3. Build command: `npm install && npm run build`
4. Start command: `npx serve dist -p $PORT`

---

## Local development

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit as needed
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # proxies /api to localhost:8000
```

---

## Project structure

```
backend/
  core/           Django project (settings, urls, wsgi)
  ingestion/
    models.py     Data model (Tenant, IngestJob, EmissionRecord, AuditEvent)
    views.py      REST API views
    serializers.py
    urls.py
    parsers/
      sap_parser.py       SAP IDoc-derived flat file
      utility_parser.py   Green Button / EnergyCAP CSV
      travel_parser.py    Concur-style JSON
    management/commands/seed_demo.py
  requirements.txt
  Procfile

frontend/
  src/
    api/client.js   Axios API client
    pages/          Dashboard, Records, Upload, Jobs, Login
    components/     Layout
    styles.css
  package.json

MODEL.md      Data model design and rationale
DECISIONS.md  Every ambiguity resolved, with reasoning
TRADEOFFS.md  Three things deliberately not built
SOURCES.md    Research on each data source format
```

---

## Sample files

Download sample files from the Upload page, or find them in `SOURCES.md`.

The parsers handle realistic data including:
- German SAP column headers and decimal formats
- Billing periods that don't align with calendar months
- SAP unit codes (MMBTU, TO, GAL)
- Estimated utility meter reads
- IATA code pairs for flight distance estimation
- Multi-currency travel expenses
