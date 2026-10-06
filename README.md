# CarHub — car marketplace for Nigeria
n[![CI](https://github.com/asgatcreation/carhub/actions/workflows/ci.yml/badge.svg)](https://github.com/asgatcreation/carhub/actions/workflows/ci.yml)

A full-stack e-commerce marketplace where buyers browse verified listings, chat with sellers and **reserve a car online with a refundable deposit**, then pay the balance after an in-person inspection. Sellers list cars in minutes, verified dealers go live instantly, and a moderation queue keeps the catalogue clean.

Built with **Django 5**, **django-allauth**, **Channels (WebSockets)** and **Paystack**, with a hand-written design system (no CSS framework) and progressive-enhancement JavaScript.

> **Portfolio project.** Listings, dealers and reviews are generated demo data; no real vehicles are sold. Car photos come from Wikimedia Commons and are credited on every listing.

---

## Highlights

**For buyers**
- Search with filters for make, body type, condition, fuel, transmission, price, year, mileage and state, plus readable "active filter" chips and a natural-language query (`2021 lexus lagos`).
- Autocomplete in the header search; an SEO-friendly listing page (JSON-LD) with a gallery and lightbox, a full spec sheet, features and a finance estimator.
- Cart and saved cars that work for guests (session) and merge into the account at sign-in.
- **Reservation checkout:** the buyer pays a ₦250,000 refundable deposit per car through Paystack, and the car is taken off the market. Rows are locked during checkout so two buyers can't reserve the same car.
- Order history with price snapshots, in-app messaging with sellers (WebSockets with an HTTP-polling fallback), and notifications.

**For sellers**
- A multi-section listing form with drag-and-drop photo upload and live previews.
- A seller dashboard with views, saves and enquiries per listing, plus mark-as-sold and relisting.
- A public seller page with ratings broken down by category and paginated reviews.
- Dealer verification applications, reviewed by staff.

**For staff**
- A moderation queue: new sellers' listings are reviewed before going live, and the seller gets an in-app notification and an email with the moderator's note.
- A customised Django admin with photo previews, bulk approve/reject and order management.

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12+, Django 5.2, django-allauth (email login, optional Google) |
| Real-time | Django Channels consumer per conversation (participants only) |
| Payments | Paystack: transaction initialise, verify, and HMAC-SHA512 webhook verification |
| Frontend | Server-rendered templates, a custom CSS design system (tokens, components), vanilla JS |
| Data | SQLite locally, Postgres via `DATABASE_URL` in production |
| Static | WhiteNoise (compressed, hashed assets) |
| Quality | 54 automated tests, GitHub Actions CI (checks, migration drift, tests, seed smoke test) |

## Architecture notes

```
config/          settings (env-driven), URLs, ASGI/WebSocket routing
core/            home, about, contact; shared formatting + template tags; context processors
cars/            catalogue, browse/search, cart, wishlist, checkout, orders, selling, moderation
  services.py    cart / wishlist / order logic shared by views, signals and context processors
  payments.py    small Paystack client
  seed/          demo catalogue + curated photo credits (photos.json)
users/           custom user (email login), profiles, messaging, notifications, seller verification
cas/, driverzone/  scaffolding for the upcoming Accessories and Hire-a-driver sections
```

Design decisions worth calling out:
- **Deposit-based checkout.** Paying ₦50M+ by card isn't realistic, so checkout reserves the car with a refundable deposit, which is how real car marketplaces work. `OrderItem` keeps a snapshot of the title and price.
- **Payments can't be faked.** Orders are only marked paid after Paystack verifies the transaction, and the amount must match. Without a provider, checkout runs only when `DEMO_CHECKOUT` is on, and those orders are labelled as demo.
- **Moderation by default.** `Car.objects.public()` (approved and not sold) is the only queryset public pages use; owners and staff can still preview pending listings.
- **Safe chat.** Conversations are participant-only (HTTP and WebSocket), and messages are rendered with `textContent`, never `innerHTML`.
- **Security headers and secrets.** All secrets come from environment variables. HTTPS, HSTS and secure cookies switch on automatically when `DEBUG` is off.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
python manage.py migrate
python manage.py seed_demo      # ~100 cars, dealers, reviews, chats and an order
python manage.py runserver
```

Then open http://localhost:8000. On Windows, `scripts\dev_setup.ps1` does all of the above in one go.

### Demo accounts

`seed_demo` creates these accounts (all use the password `CarHubDemo!2026`). When `SHOW_DEMO_LOGINS=True`, the sign-in page offers them as one-click buttons:

| Role | Email | What to try |
| --- | --- | --- |
| Buyer | `buyer@carhub.demo` | Saved cars, cart → checkout, order history, messages |
| Verified dealer | `harborpoint@carhub.demo` | Seller dashboard, edit a listing, reply to buyers |
| Moderator (staff) | `moderator@carhub.demo` | Moderation queue, seller applications |

The moderator is deliberately **not** a superuser. Create your own admin with `python manage.py createsuperuser`. To restore pristine demo data at any time, run `python manage.py seed_demo --reset`.

### Payments

Put your Paystack **test** keys in `.env` (`PAYSTACK_SECRET_KEY`) to go through the real hosted checkout; Paystack's test cards work. Point the Paystack webhook at `/cars/webhooks/paystack/`. Without keys, `DEMO_CHECKOUT=True` records clearly labelled demo reservations.

### Real-time chat

`runserver` serves HTTP only, so chat falls back to polling every few seconds. For live WebSocket chat, run an ASGI server and set `CHAT_WEBSOCKETS=True`:

```bash
pip install daphne
daphne config.asgi:application
```

With more than one process, also set `REDIS_URL` and install `channels-redis`.

## Deploying (Render)

The repo includes a [`render.yaml`](render.yaml) blueprint for a free Render web service:

1. Push the repo to GitHub.
2. In Render, choose **New → Blueprint** and select the repository. Render reads `render.yaml`, generates `DJANGO_SECRET_KEY` and asks for the optional Paystack keys.
3. Deploy. The build runs `build.sh` (install and `collectstatic`). On start, the app migrates, seeds the demo data when the database is empty, and serves HTTP and WebSockets with **daphne**.

By default the demo uses SQLite on the instance's disk, so it **resets to fresh demo data on every deploy or restart**, which suits a public demo. To keep data, add a Postgres database and set `DATABASE_URL`. Uploaded photos are served by Django (`SERVE_MEDIA=True`), which is fine at demo scale; use S3 or Cloudinary in real production.

## Tests

```bash
python manage.py test
```

The suite covers search and filters, moderation visibility, the guest-to-account cart merge, demo and Paystack checkout (mocked), webhook signature and amount checks, the race where a car is reserved during checkout, listing creation with uploads, reviews, conversation privacy, and HTML escaping in chat. It also includes regression tests for bugs fixed during the rebuild: a checkout that completed without payment, and a thumbnail recursion.

## Photo credits

Vehicle photos are hotlinked from [Wikimedia Commons](https://commons.wikimedia.org/) under their respective Creative Commons or public-domain licences. Each listing shows the photographer and licence under the gallery. `python manage.py fetch_car_photos` shows how the set was collected; the committed `cars/seed/photos.json` was then curated by hand so every photo matches the listing's model generation.

## Roadmap

- Persistent Postgres + Cloudinary uploads for the hosted demo
- Accessories store and Hire-a-driver (models scaffolded in `cas/` and `driverzone/`)
- Saved searches with email alerts, and side-by-side car comparison
- Refund flow for cancelled reservations (Paystack refunds API)
