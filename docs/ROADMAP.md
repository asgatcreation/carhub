CarHub Roadmap (High Level)
============================

Generated: 2026-01-03

Overview
--------
This roadmap breaks the full platform into milestones across the phases you described. Each milestone includes acceptance criteria and suggested tasks.

Phase 1 — Analysis & Foundation (Current)
----------------------------------------
- Inventory & ER diagram (done)
- Settings & environment checklist (done)
- Authentication, `allauth` integration stabilized (defensive settings added)
- Quick UX fixes applied (auth modal, avatar persistence, cart session normalization)

Acceptance criteria:
- Project boots locally with no import-time failures
- Migrations run cleanly
- Auth modal shows and social login links render (safe fallback)

Phase 2 — Car App Perfection
----------------------------
Milestones:
1. Gallery & media reliability
   - Async thumbnailing, background worker
   - Ensure `ProfileImage` migrations applied
2. Comparison engine
   - API endpoint to build side-by-side comparisons
   - UI component for comparing up to 4 cars
3. 360° Virtual Tours
   - VirtualTour models and upload pipeline
4. Advanced search & filters
   - Integrate Postgres full-text or Elasticsearch

Acceptance criteria:
- Comparison UI functional, tests pass
- Search returns relevant results in <200ms for moderate dataset

Phase 3 — CAS App
------------------
- Complete product catalog & seller dashboard
- Order & inventory management
- Checkout integration (Stripe/Paystack)

Phase 4 — Driverzone
---------------------
- Driver listings and booking flows
- Dispatch dashboard and scheduling

Phase 5 — User App
------------------
- Multi-role dashboards and permissions
- Real-time chat and notifications
- KYC/application workflow

Phase 6 — Admin Dashboard
-------------------------
- Real-time analytics + task queues
- Bulk operations and safe DB tweaks

Phase 7 — Integration & Testing
--------------------------------
- End-to-end tests, load testing, security hardening
- Deployment to staging and production

Timeline & Estimates (Rough)
----------------------------
- Phase 1: 1-2 weeks (foundation)
- Phase 2: 4-8 weeks
- Phase 3: 4-6 weeks
- Phase 4: 4-6 weeks
- Phase 5: 4-8 weeks
- Phase 6: 3-6 weeks
- Phase 7: 2-4 weeks

Notes
-----
- Prioritize DB and search design early (Postgres + Elasticsearch) to avoid large-scale refactors.
- Add CI early to run migrations and tests on PRs.
