# Invoice Manager MVP

Full-stack invoice management MVP for small businesses and freelancers.

## Stack

- Backend: Django, Django REST Framework, PostgreSQL, Celery, Redis
- Frontend: Next.js App Router, TypeScript, React Query
- Config: environment-variable based
- Background jobs: scheduled reminders and recurring invoice generation
- Authentication: Django session auth with CSRF-protected REST endpoints

## Phase 2 additions

- Public EFT payment pages at `/pay/{token}`
- Partial payments with invoice payment history
- Email and WhatsApp reminder channels
- Recurring invoice templates with scheduled generation
- Reusable owner banking profiles with per-invoice EFT snapshots

## Authentication architecture

- Backend auth uses Django's built-in user model with email-based sign-in.
- The app uses server-side Django sessions instead of JWTs.
- Internal API routes require an authenticated session by default.
- The frontend sends credentials with every internal API request and includes the CSRF token for unsafe requests.
- Password reset uses Django's secure, time-limited token generator and sends reset links to the frontend route at `/reset-password`.
- Registration can optionally create the user's first reusable banking profile, but banking setup is never required to create an account.
- The public EFT payment flow at `/pay/{token}` and `/api/public/pay/{token}/` remains accessible without login.

This approach fits the existing browser-based architecture cleanly:

- no token storage in localStorage
- backend keeps authentication state and password security logic
- frontend only needs session bootstrap plus route gating

## Folder structure

```text
invoice-manager/
  backend/
    apps/
      clients/      Client model
      contractors/  Optional contractor records used by recurring templates
      invoices/     Invoice domain, API, services, seed command, tests
      reminders/    Reminder channel services and Celery tasks
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
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

The backend loads `backend/.env` automatically at startup. Values already present in the shell environment still take precedence.

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

## Backend auth routes

- `GET /api/auth/csrf/`
- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `POST /api/auth/forgot-password/`
- `POST /api/auth/reset-password/`
- `GET /api/auth/me/`

All `/api/auth/*` routes are public except:

- `POST /api/auth/logout/`
- `GET /api/auth/me/`

All internal invoice, recurring, client, contractor, payment, and dashboard routes require authentication by default.

## Frontend setup

1. Copy `frontend/.env.example` to `frontend/.env`.
2. Install dependencies and start the app:

```bash
cd frontend
npm install
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000).

The frontend reads `frontend/.env`, and the invoice form will follow the browser's locale for decimal formatting. For example, some users will see `1,00` instead of `1.00`. In the line-item editor:

- `Quantity` is the number of units being billed.
- `Unit price` is the price for one unit.
- `Line total` is calculated in the UI as `quantity x unit price`.

## Auth flow in the frontend

Pages added:

- `/login`
- `/register`
- `/forgot-password`
- `/reset-password`

Protected routes:

- `/`
- `/dashboard`
- `/invoices/*`
- `/recurring-invoices/*`
- `/settings/banking-details`

Public routes:

- `/login`
- `/register`
- `/forgot-password`
- `/reset-password`
- `/pay/{token}`

Unauthenticated users are redirected to `/login`, and protected page content is held behind an auth bootstrap loading state so internal content does not flash before redirect.

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
- `POST /api/invoices/{id}/remind/`
- `GET /api/invoices/{id}/payments/`
- `POST /api/invoices/{id}/payments/`
- `PATCH /api/payments/{id}/`
- `POST /api/invoices/{id}/payment-page/regenerate-token/`
- `GET /api/invoices/{id}/eft-details/`
- `PUT /api/invoices/{id}/eft-details/`
- `GET /api/invoices/{id}/pdf/`
- `GET /api/banking-profiles/`
- `POST /api/banking-profiles/`
- `PATCH /api/banking-profiles/{id}/`
- `DELETE /api/banking-profiles/{id}/`
- `POST /api/banking-profiles/{id}/set-default/`
- `GET /api/public/pay/{token}/`
- `GET /api/recurring-invoices/`
- `POST /api/recurring-invoices/`
- `PATCH /api/recurring-invoices/{id}/`
- `DELETE /api/recurring-invoices/{id}/`
- `GET /api/line-items/?invoice={invoice_id}`

## Example auth payloads

Register:

```json
{
  "email": "owner@example.com",
  "password": "StrongPass123!",
  "confirm_password": "StrongPass123!",
  "first_name": "Ava",
  "last_name": "Owner",
  "banking_profile": {
    "profile_name": "Primary operating account",
    "account_holder_name": "Ava Owner Pty Ltd",
    "bank_name": "FNB",
    "account_number": "12345678901",
    "account_type": "Business Cheque",
    "branch_code": "250655",
    "default_payment_reference": "AVA-PRIMARY"
  }
}
```

Login:

```json
{
  "email": "owner@example.com",
  "password": "StrongPass123!"
}
```

Forgot password:

```json
{
  "email": "owner@example.com"
}
```

Reset password:

```json
{
  "uid": "Mg",
  "token": "czt6ir-7ddc0f5f3d9f6a2f0b4f2f7b2f3d4e90",
  "password": "EvenStronger123!",
  "confirm_password": "EvenStronger123!"
}
```

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
  "payment_page_enabled": true,
  "client": {
    "name": "Atlas Creative",
    "email": "billing@atlas.test",
    "address": "54 Main Road",
    "phone_number": "+27123456789"
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

Example invoice EFT setup using a saved profile:

```json
{
  "mode": "saved_profile",
  "banking_profile_id": 3,
  "payment_reference": "INV-2026-010"
}
```

Example invoice EFT setup using manual details:

```json
{
  "mode": "manual",
  "profile_name": "One-off account",
  "account_holder_name": "Ava Owner Pty Ltd",
  "bank_name": "ABSA",
  "account_number": "4096150463",
  "account_type": "Business Cheque",
  "branch_code": "632005",
  "payment_reference": "INV-2026-010"
}
```

## Example record-payment payload

```json
{
  "amount": "500.00",
  "payment_date": "2026-04-05",
  "payment_method": "eft",
  "reference": "ATLAS-DEP-001",
  "notes": "First partial payment received."
}
```

## Example reminder payload

```json
{
  "channel": "whatsapp"
}
```

## Example recurring-invoice payload

```json
{
  "template_name": "Monthly Retainer",
  "client_id": 1,
  "contractor_id": 1,
  "frequency": "monthly",
  "start_date": "2026-04-05",
  "status": "active",
  "currency": "USD",
  "payment_terms_days": 14,
  "tax_type": "percentage",
  "tax_rate": "15.00",
  "notes": "Generated automatically.",
  "line_items_template": [
    {
      "description": "Retainer",
      "quantity": "1.00",
      "unit_price": "950.00"
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

- Email + password authentication is required for all internal app routes and internal API access.
- Password reset emails always return a safe generic response, even for unknown email addresses.
- Password reset links are time-limited using Django's secure token generator.
- Session auth requires frontend requests to include credentials and CSRF headers for unsafe methods.
- Users may have zero, one, or many reusable banking profiles.
- Invoice payment pages use an invoice-level EFT snapshot, not live mutable banking profiles.
- Editing a saved banking profile later does not silently change historical invoices that already copied it.

- Due date cannot be before issue date.
- Quantity must be a whole-number unit and unit price cannot be negative.
- Payment amounts must be greater than zero.
- Total recorded payments cannot exceed the invoice total.
- Decimal values may render with a comma or period depending on the user's browser locale, but the numeric meaning is the same.
- Line totals, subtotal, tax, and grand total are recalculated server-side.
- Paid, outstanding, and overdue states are derived server-side from due dates and recorded payments.
- Public payment pages only expose invoice summary data plus EFT details and are hidden when disabled.
- Public payment pages return EFT instructions only when the invoice has a saved snapshot attached.
- WhatsApp reminders fail fast when the client has no phone number or no provider is configured.
- Recurring invoices generate draft invoices and advance `next_run_date` without duplicating the same cycle.

## Tests

Run backend tests with:

```bash
cd backend
python manage.py test
```

The included tests cover:

- invoice total recalculation
- partial payment aggregation and status transitions
- public EFT payment page access and invalid token handling
- banking profile CRUD and default-profile rules
- optional banking-profile registration flow
- invoice EFT snapshot creation and switching between saved/manual modes
- dashboard summary outstanding-balance flow
- email and WhatsApp reminder dispatch behavior
- recurring invoice generation and duplicate prevention
- invoice PDF response generation

## PDF generation

- PDFs are generated on demand by the backend using `reportlab`.
- Use `GET /api/invoices/{id}/pdf/` to download a rendered invoice PDF.
- The invoice detail page exposes a `Download PDF` action.

## Payment pages and reminders

- Each invoice gets a secure `public_token` and an optional public payment page under `/pay/{token}`.
- Owners can manage reusable banking profiles at `/settings/banking-details`.
- When an invoice uses EFT, the owner either selects a saved profile or enters manual one-off details for that invoice.
- The selected profile is copied into the invoice snapshot; the public page never reads directly from mutable profile rows.
- The internal invoice detail page exposes copy/open actions plus token regeneration for payment pages.
- Public payment pages show invoice totals, amount already paid, outstanding balance, EFT banking details, and the payment reference.
- `POST /api/invoices/{id}/remind/` accepts `email` or `whatsapp`.
- WhatsApp delivery is provider-based. Local development can use `WHATSAPP_PROVIDER=console`, while production can use `WHATSAPP_PROVIDER=twilio`.

## Seed data

`python manage.py seed_invoice_data` now creates:

- demo and `solifas@extratrx.com` owner accounts
- a default reusable banking profile for each seeded owner
- an invoice using a saved-profile EFT snapshot
- an invoice using manual invoice-only EFT details
- a fully paid invoice with recorded payment history
- a contractor record used by a recurring invoice template
- a recurring invoice template ready for scheduler testing

## Extensibility notes

The backend is structured around domain apps plus service/selectors layers so later additions such as authentication, PDFs, richer reminder providers, recurring invoice automation, and multi-user support can be added without rewriting invoice logic.
