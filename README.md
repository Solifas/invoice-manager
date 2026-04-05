# Invoice Manager MVP

Full-stack invoice management MVP for small businesses and freelancers.

## Stack

- Backend: Django, Django REST Framework, PostgreSQL, Celery, Redis
- Frontend: Next.js App Router, TypeScript, React Query
- Config: environment-variable based
- Background jobs: scheduled and manual reminder emails

## Folder structure

```text
invoice-manager/
  backend/
    apps/
      clients/      Client model
      invoices/     Invoice domain, API, services, seed command, tests
      reminders/    Email reminder services and Celery tasks
    config/         Django settings, URLs, Celery bootstrap
  frontend/
    src/app/        Dashboard and invoice pages
    src/components/ Reusable layout, dashboard, and invoice UI
    src/lib/        API client and shared types
  docker-compose.yml
```

## Backend setup

1. Copy `backend/.env.example` to `backend/.env`.
2. Create a PostgreSQL database and Redis instance, or use Docker.
3. Install dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

4. Run migrations and seed data:

```bash
python manage.py migrate
python manage.py seed_invoice_data
```

5. Start the API:

```bash
python manage.py runserver
```

6. Start Celery worker and beat in separate terminals:

```bash
celery -A config worker -l info
celery -A config beat -l info
```

## Frontend setup

1. Copy `frontend/.env.example` to `frontend/.env`.
2. Install dependencies and start the app:

```bash
cd frontend
npm install
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000).

## Docker setup

1. Copy the example env files:

```bash
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

2. Start everything:

```bash
docker compose up --build
```

## Core API routes

- `GET /api/invoices/`
- `POST /api/invoices/`
- `GET /api/invoices/{id}/`
- `PUT /api/invoices/{id}/`
- `DELETE /api/invoices/{id}/`
- `GET /api/invoices/dashboard-summary/`
- `POST /api/invoices/{id}/send-reminder/`
- `GET /api/invoices/{id}/pdf/`
- `GET /api/line-items/?invoice={invoice_id}`

## Example invoice payload

```json
{
  "invoice_number": "INV-2026-010",
  "issue_date": "2026-04-04",
  "due_date": "2026-04-18",
  "status": "sent",
  "notes": "Thanks for your business.",
  "currency": "USD",
  "tax_type": "percentage",
  "tax_rate": "15.00",
  "client": {
    "name": "Atlas Creative",
    "email": "billing@atlas.test",
    "address": "54 Main Road"
  },
  "line_items": [
    {
      "description": "Website redesign",
      "quantity": "1.00",
      "unit_price": "1500.00"
    },
    {
      "description": "SEO support",
      "quantity": "2.00",
      "unit_price": "250.00"
    }
  ]
}
```

## Example dashboard response

```json
{
  "total_invoices": 12,
  "unpaid_invoices": 7,
  "overdue_invoices": 2,
  "total_amount_outstanding": "8240.00"
}
```

## Validation and business rules

- Due date cannot be before issue date.
- Quantity and unit price cannot be negative.
- Line totals, subtotal, tax, and grand total are recalculated server-side.
- Overdue invoices are derived from due dates when invoices are recalculated.

## Tests

Run backend tests with:

```bash
cd backend
python manage.py test
```

The included tests cover:

- invoice total recalculation
- nested invoice creation via API
- dashboard summary API flow
- invoice PDF response generation

## PDF generation

- PDFs are generated on demand by the backend using `reportlab`.
- Use `GET /api/invoices/{id}/pdf/` to download a rendered invoice PDF.
- The invoice detail page exposes a `Download PDF` action.

## Extensibility notes

The backend is structured around domain apps plus service/selectors layers so later additions such as authentication, PDFs, recurring invoices, payment links, and multi-user support can be added without rewriting invoice logic.
