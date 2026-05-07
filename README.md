# AI_Agents_For_Outsourcing

This repo currently includes:

- Postgres via `docker-compose.yml`
- Database schema in `db/schema.sql`
- FastAPI backend (authentication + authorization helpers) under `app/`
- Server-rendered web pages served by FastAPI at `/`

The active UI is the FastAPI/Jinja application served by `uvicorn` on port `8000`.
The old React/Vite and Flask prototype UIs have been removed from this branch.

## Local Setup

1) Start Postgres

`docker compose up -d`

2) Install Python deps

`pip install -r requirements.txt`

3) Configure env

- Copy `.env.example` to `.env`
- Fill in `JWT_SECRET`
- (Optional) Fill in `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` for Google login
- (Optional) Fill in `OPENROUTESERVICE_API_KEY` to enable meeting travel-time warnings
- (Optional) Fill in `ORGANIZATION_DEFAULT_LOCATION` and coordinates for the final travel-origin fallback

4) Run API

`uvicorn app.main:app --reload`

API docs: `http://127.0.0.1:8000/docs`
Web login page: `http://127.0.0.1:8000/`

## Production Notes

For a public deployment, set:

- `APP_ENV=production`
- a strong `JWT_SECRET` of at least 32 characters
- `COOKIE_SECURE=true`
- `CSRF_PROTECTION_ENABLED=true`
- `APP_BASE_URL` to the public HTTPS URL

The app refuses to start in production if these safety settings are missing or still set to local-development defaults.

## Travel-Time Warnings

The meetings page can now evaluate travel feasibility between meetings using `openrouteservice` routing and OpenStreetMap-based geocoding.

Relevant environment variables:

- `OPENROUTESERVICE_API_KEY`
- `OPENROUTESERVICE_BASE_URL` (defaults to `https://api.openrouteservice.org`)
- `OPENROUTESERVICE_TIMEOUT_SECONDS`
- `OPENROUTESERVICE_PROFILE` (defaults to `driving-car`)
- `TRAVEL_WARNING_BUFFER_MINUTES`
- `TRAVEL_WARNING_TIGHT_WINDOW_MINUTES`
- `ORGANIZATION_DEFAULT_LOCATION`
- `ORGANIZATION_DEFAULT_LOCATION_LATITUDE`
- `ORGANIZATION_DEFAULT_LOCATION_LONGITUDE`

If the ORS provider is unavailable or a meeting location cannot be resolved, the page continues rendering without travel warnings.

## Auth Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh` (rotates refresh token cookie)
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/google/exchange`
- `POST /auth/link/google`

## Recommendation Endpoint

- `POST /recommendations/meeting-times`
  - Finds optimal meeting slots for attendees using:
  - Existing meeting conflicts (owned calendar + invited/accepted meetings)
  - `time_slot_preferences` windows

Example payload:

```json
{
  "attendee_emails": ["alice.demo@example.com", "bob.demo@example.com", "carol.demo@example.com"],
  "window_start": "2026-03-10T08:00:00Z",
  "window_end": "2026-03-10T18:00:00Z",
  "duration_minutes": 60,
  "slot_interval_minutes": 30,
  "max_results": 5,
  "include_current_user": true
}
```

Optional demo seed data:

```bash
psql -U appuser -d appdb -f db/seed_recommendation_demo.sql
```

If `psql` is not on your PATH, run the Python seed runner instead:

```bash
py -3.14 db/seed_recommendation_demo.py
```

## Notes

- Refresh token is stored in an `HttpOnly` cookie (path `/auth`).
- Access token is returned in JSON and should be sent as `Authorization: Bearer <token>`.
- Google auth has not yet been tested.
