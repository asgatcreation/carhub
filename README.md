<div align="center">

# CarHub

**Nigeria's marketplace for verified cars. Reserve online with a refundable deposit, inspect in person, then pay the balance.**

[![CI](https://github.com/asgatcreation/carhub/actions/workflows/ci.yml/badge.svg)](https://github.com/asgatcreation/carhub/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-0C4B33?logo=django&logoColor=white)
![Tests](https://img.shields.io/badge/tests-93%20passing-11845b)

**[Live demo →](https://carhub-es73.onrender.com/)** &nbsp;·&nbsp; [Buyer journey](#the-buyer-journey) &nbsp;·&nbsp; [Features](#features) &nbsp;·&nbsp; [Run it locally](#run-it-locally) &nbsp;·&nbsp; [Architecture](#architecture)

<img src="docs/screenshots/01-home.jpg" alt="CarHub home page with the featured-car spotlight hero" width="100%">

</div>

> **Portfolio project** by **[Akanji Oluwaseun Gabriel](https://github.com/asgatcreation)**, built as the e-commerce case study in my portfolio. Listings, dealers and reviews are generated demo data and no real vehicles are sold. Car photos come from Wikimedia Commons and are credited on every listing.
>
> The live demo runs on Render's free tier: the first visit after a quiet spell takes about 30–50 seconds to wake up, and the data resets on every deploy. Use the one-click demo accounts on the sign-in page.

---

## Why this project

Buying a car online in Nigeria usually means scrolling through unverified listings, then wiring money to a stranger. Nobody pays ₦50M by card for a car they haven't seen, so CarHub models how the purchase really works:

1. **Every listing is reviewed** before it goes live, and every price is compared against the market.
2. Buyers **reserve with a refundable ₦250,000 deposit**, which takes the car off the market.
3. The seller **confirms an inspection slot**. The buyer inspects with their own mechanic, then **pays the balance** or cancels for a refund.

Each step has a real status, notification and email behind it, from the deposit through to the sale.

## The buyer journey

| | |
| :-- | :-- |
| <img src="docs/screenshots/02-browse.jpg" alt="Browse with filters"> | <img src="docs/screenshots/03-car-detail.jpg" alt="Car page with price insight"> |
| **1. Find a car.** Filters for make, body, condition, fuel, price, year, mileage and state, plus a natural-language search (`2021 lexus lagos`). Every card shows an estimated monthly payment and a **price badge** comparing it with the market. | **2. Judge the price.** The car page compares the asking price with similar listings, adjusted for model year, and shows where it falls in the market range. The buy box shows exactly what is due today. |
| <img src="docs/screenshots/04-sign-in.jpg" alt="Sign in to reserve"> | <img src="docs/screenshots/05-checkout-details.jpg" alt="Checkout details step"> |
| **3. Sign in to reserve.** Guests are asked to sign in (email or **Google**) and land straight back in checkout with the car already in their cart. | **4. Your details.** The email is locked to the account email so receipts can't be misdirected. The buyer picks an inspection state, a date and a time slot. |
| <img src="docs/screenshots/06-review-and-pay.jpg" alt="Review and pay"> | <img src="docs/screenshots/07-confirmation.jpg" alt="Confirmation and order tracking"> |
| **5. Review & pay.** Each section has an Edit link. The summary separates the total price, the refundable deposit due today and the balance due at inspection. Paystack, or a clearly labelled demo payment. | **6. Track it.** Every car in an order gets its own timeline: deposit paid → inspection scheduled → balance paid. Cancelling releases the car and refunds the deposit. |

### The other side of the marketplace

| | |
| :-- | :-- |
| <img src="docs/screenshots/08-seller-reservations.jpg" alt="Seller reservations"> | <img src="docs/screenshots/09-moderation.jpg" alt="Moderation workspace"> |
| **Seller reservations.** Dealers see each buyer's preferred slot, confirm or reschedule the inspection, then mark the sale complete (the car becomes sold). The buyer is notified in-app and by email at each step. | **Moderation workspace.** New sellers' listings wait for review, alongside photos, key facts, the seller's history, automatic quality checks and the price compared with the market. One-click rejection reasons; approving or rejecting doesn't reload the page. |
| <img src="docs/screenshots/10-seller-storefront.jpg" alt="Seller storefront"> | <img src="docs/screenshots/14-dark-mode.jpg" alt="Dark mode"> |
| **Seller storefront.** A public page with stats, inventory filtered by brand and sorted, recently sold cars, rating breakdowns and reviews. | **Dark mode.** Follows the system setting, with a toggle that remembers the visitor's choice. Built on the same design tokens. |

### Admin console: everything public is checked first

| | |
| :-- | :-- |
| <img src="docs/screenshots/15-admin-console.jpg" alt="Admin console overview"> | <img src="docs/screenshots/16-review-moderation.jpg" alt="Review moderation"> |
| **Staff console at `/staff/`.** A branded sign-in that only lets staff through (Django admin's sign-in redirects here too). The overview shows each review queue, live marketplace numbers and recent activity. | **Review queues.** Listings, buyer reviews, new photos, and dealer, driver and vendor verifications. Reviews are flagged automatically when they contain phone numbers or links, and show whether the reviewer actually bought from the seller. Every decision notifies the person in-app and by email. |

### Accounts secured with one-time codes

| | |
| :-- | :-- |
| <img src="docs/screenshots/11-verify-code.jpg" alt="Enter the 6-digit code"> | <img src="docs/screenshots/12-email-code.jpg" alt="Verification email" width="80%"> |
| New accounts verify their email with a **6-digit code**, and forgotten passwords are reset the same way. The code boxes accept typing, pasting and autofill, and submit automatically once complete. | Branded HTML emails (with a plain-text fallback). **The code never appears in the subject line or inbox preview**, only inside the opened email. Codes expire (15 minutes for sign-up, 10 for resets), work once, and are rate-limited. |

### On a phone

<img src="docs/screenshots/13-mobile.jpg" alt="CarHub on mobile" width="100%">

Every screen is designed for a 390px-wide phone first. Car sections become swipeable rails, the buy box becomes a sticky bottom bar, and filters open in a drawer. No page scrolls sideways.

## Features

**Buyers**
- Search, filters, sorting and header autocomplete; SEO-friendly car pages (JSON-LD) with a gallery, lightbox, spec sheet and finance estimate.
- Price insight on every car (great, good, fair or high), based on same-model comparables normalised for year.
- Saved cars and a cart that work for guests and merge into the account at sign-in.
- A four-step checkout (cart → details → review & pay → confirmed) with row locking, so two buyers can never reserve the same car.
- Per-car order tracking, cancellation with refund, in-app chat with sellers (WebSockets with a polling fallback), and notifications.

**Sellers**
- A listing form with drag-and-drop photos. Verified dealers go live instantly; new sellers go to moderation.
- A dashboard with views, saves and enquiries; a reservations inbox for scheduling inspections and completing sales.
- A public storefront with ratings broken down by category.

**Staff**
- A front-end admin console (`/staff/`) with its own branded sign-in, dark sidebar and live queue counts.
- Pre-publication moderation of listings from new sellers and of every buyer review; spot checks of new photos; verification of dealers, drivers and accessory vendors (approve, reject or request changes).
- The Django admin stays available to superusers for raw data work.

**Accounts**
- Email and password, or **Continue with Google**. Both lead to the same account: Google signs in an existing email account, and Google-only users can add a password through "Forgot password".
- Email verification and password reset by one-time code, with security emails on password changes.
- Sign-out keeps you on the page you were on, or sends you home from private pages.

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12+, Django 5.2, django-allauth (email + Google, one-time codes) |
| Real-time | Django Channels: one participant-only WebSocket consumer per conversation |
| Payments | Paystack: initialise, verify, HMAC-SHA512 webhook, refunds |
| Email | Branded HTML templates; SMTP (e.g. Gmail app password) or Brevo's HTTP API |
| Frontend | Server-rendered templates, a hand-written CSS design system (tokens, dark theme), vanilla JS with progressive enhancement |
| Data | SQLite locally, Postgres via `DATABASE_URL` |
| Hosting | Render (daphne ASGI), WhiteNoise static files |
| Quality | 93 automated tests, GitHub Actions CI on Python 3.12 and 3.13 |

## Architecture

```
config/            settings (all from env), URLs, ASGI + WebSocket routing
core/              home, about, contact · formatting + template tags · branded email helper · Brevo backend
cars/              catalogue, search, cart, wishlist, checkout, orders, reservations, selling, moderation
  services.py      cart, orders, reservation lifecycle, notifications and price insight, shared by views
  payments.py      small Paystack client (initialise, verify, webhook signature, refund)
  seed/            demo catalogue + curated photo credits
users/             custom user (email login), profiles, chat, notifications, seller verification
  adapter.py       numeric one-time codes, email context
templates/emails/  responsive HTML email layout used by every email
cas/, driverzone/  scaffolding for the upcoming Accessories store and Hire-a-driver
```

Decisions worth calling out:
- **Reservations, not card payments for the whole car.** `OrderItem` has its own lifecycle (`reserved → scheduled → completed`, or `cancelled` with a refund status) and snapshots the title and price, because a car on one order can be cancelled while another proceeds.
- **Payments can't be faked.** An order is marked paid only after Paystack verifies the transaction and the amount matches. Without a provider, checkout runs only when `DEMO_CHECKOUT` is on, and those orders are labelled as demo.
- **Moderation by default.** Public pages only use `Car.objects.public()`, which returns approved cars that aren't sold.
- **Codes stay out of the inbox preview.** The subject line and the hidden preheader carry no code.
- **Verification fails safe.** It is mandatory only when email delivery is configured, so a deploy without SMTP never locks users out. Existing accounts were marked verified by a data migration.
- **Safe chat.** Conversations are participant-only over HTTP and WebSocket, and messages are rendered with `textContent`.

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
python manage.py migrate
python manage.py seed_demo      # 108 cars, dealers, reviews, chats and reservations at every stage
python manage.py runserver
```

Open http://localhost:8000. On Windows, `scripts\dev_setup.ps1` does all of this in one step.

### Demo accounts

All demo accounts use the password `CarHubDemo!2026`, and the sign-in page offers them as one-click buttons:

| Role | Email | What to try |
| --- | --- | --- |
| Buyer | `buyer@carhub.demo` | Orders at every stage, saved cars, checkout, messages |
| Verified dealer | `harborpoint@carhub.demo` | Reservations to confirm, a scheduled inspection, completed and cancelled sales |
| Moderator (staff) | `moderator@carhub.demo` | Admin console at `/staff/`: listings, reviews, photos, verifications |

The moderator is deliberately **not** a superuser. To restore fresh demo data, run `python manage.py seed_demo --reset`.

### Optional integrations

| Feature | Setting | Notes |
| --- | --- | --- |
| Email (codes, receipts) | `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | For Gmail, enable 2-Step Verification and create an [App Password](https://myaccount.google.com/apppasswords). On hosts that block SMTP, set `BREVO_API_KEY` instead. Without either, emails print to the console. |
| Google sign-in | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Authorised redirect URI: `<your site>/accounts/google/login/callback/` |
| Paystack | `PAYSTACK_SECRET_KEY` | Test keys work with Paystack's test cards. Webhook URL: `/cars/webhooks/paystack/` |
| Live chat | `CHAT_WEBSOCKETS=True` + daphne | `runserver` falls back to polling |
| Your admin login | `ADMIN_EMAIL`, `ADMIN_PASSWORD` | `python manage.py ensure_admin` creates or updates the superuser. It runs on every Render start, because the demo database is rebuilt on each deploy. |

## Deploying to Render

[`render.yaml`](render.yaml) describes a free web service: **New → Blueprint**, pick the repo, then fill in the optional keys above under **Environment**. The build runs `build.sh`. On start the app migrates, seeds demo data if the database is empty, and serves HTTP and WebSockets with daphne. The SQLite demo resets on every deploy; set `DATABASE_URL` to a Postgres database to keep data.

## Tests

```bash
python manage.py test
```

93 tests cover:
- Search and filters, moderation visibility and price insight.
- The guest → sign-in → checkout hand-off and the cart merge.
- Each checkout step: date validation, the locked email, exact totals, demo and mocked Paystack payments, and a car reserved by someone else mid-checkout.
- The reservation lifecycle (schedule, complete, cancel, refund, seller-only actions).
- Webhook signatures, the email-code sign-up and password-reset flows (including that codes stay out of subjects and previews), chat privacy, and regression tests for bugs fixed during the rebuild.

## Roadmap

- **Accessories store (CAS):** parts and accessories from verified vendors, matched to the buyer's car (next up)
- Hire-a-driver (DriverZone)
- Persistent Postgres + Cloudinary uploads for the hosted demo
- Saved searches with email alerts, and side-by-side comparison

## Credits

Designed and built by **Akanji Oluwaseun Gabriel** ([@asgatcreation](https://github.com/asgatcreation)).
Vehicle photos: [Wikimedia Commons](https://commons.wikimedia.org/) contributors under Creative Commons or public-domain licences, credited on each listing.
