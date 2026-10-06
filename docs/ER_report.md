ER Report — CarHub
====================

Generated: 2026-01-03
Source files inspected: `users/models.py`, `cars/models.py`, `core/models.py`
Reference DOT diagram: `docs/ER_diagram.dot`

Overview
--------
This report summarizes the primary models and relationships in the repository, highlights missing indexes or constraints, and gives recommendations for schema and performance improvements to support the full platform scope.

High-level entities
-------------------
- CustomUser (users.CustomUser)
- Profile (users.Profile)
- ProfileImage (users.ProfileImage)
- Application (users.Application)
- Conversation, Message (users)

- Car (cars.Car)
- CarImage, CarVideo (cars)
- CarCategory, Feature, AvailableBrand
- CarComparison, ComparisonItem, ComparisonCategory, CarComparisonScore
- VirtualTour, TourImage, TourVideo

- CarSellerProfile, SellerAnalytics

- MultiCart, MultiCartItem
- Cart, CartItem
- WishlistItem
- SavedItem

- Advertisement, SearchQuery, UserCarView

Primary Keys and FKs
--------------------
- `CustomUser` uses `AbstractUser` (PK: id)
- `Profile` OneToOne -> `CustomUser` (FK: user)
- `ProfileImage` FK -> `Profile` (many images per profile)
- `Application` FK -> `CustomUser` (applicant)
- `Conversation` M2M participants -> `CustomUser`
- `Message` FK -> `Conversation` and FK -> `CustomUser` (sender)

- `Car` has FK `created_by` -> `CustomUser`
- `CarImage`, `CarVideo` FK -> `Car`
- `CarCategory` M2M `Car.categories`
- `Feature` M2M `Car.features`

- `MultiCart` FK -> `CustomUser`
- `MultiCartItem` FK -> `MultiCart` (generic content_type/object_id pattern implemented as strings)

- `Cart` FK -> `CustomUser` (nullable, session_key fallback)
- `CartItem` FK -> `Cart` and FK -> `Car`

- `WishlistItem` FK -> `CustomUser` and FK -> `Car`
- `SavedItem` FK -> `CustomUser` and FK -> `Car`

Indexes & constraints observed
-----------------------------
- `Car` has multiple DB indexes in `Meta.indexes` (slug, brand/model, price, year, views_count, created_by, is_360_available, comparison_rating, status). Good coverage for listing/filtering and admin.
- `CarCategory.slug` and `Car.slug` are unique. `AvailableBrand.brand` is unique.
- `CartItem` has `unique_together = ('cart', 'car')`.
- `ComparisonItem` and `CarComparisonScore` have `unique_together` constraints.

Identified gaps & recommendations
---------------------------------
1) Foreign key indexes
   - Ensure all ForeignKey fields used in joins and filters are indexed. Django automatically creates indexes for FK fields, but verify for any `models.ForeignKey(..., db_index=False)` explicit settings. In our inspected code, FK fields look standard (indexed).

2) Frequently queried fields
   - Add/verify indexes for:
     - `Profile.user` (OneToOne, usually indexed by PK)
     - `Profile.is_car_seller_approved`, `is_cas_seller_approved`, `is_pilot_approved` if used in filters for dashboards (partial indexes might be better)
     - `Car.status`, `Car.stock`, `Car.featured` — add indexes if used in frequent queries.

3) Cart totals and denormalized price
   - `CartItem.price` is stored as DecimalField (good). Ensure application consistently sets `CartItem.price` at time of add (keep historical price) instead of reading `Car.price` at render time.
   - Add an index on `CartItem.cart` and consider indexing `CartItem.car` for lookups.

4) MultiCart generic references
   - `MultiCartItem` uses a string `content_type` and `object_id`. Consider switching to `GenericForeignKey` via `contenttypes` for a standard approach or store `content_type_id` FK to `django_content_type` for referential integrity.

5) Full-text search
   - For advanced search and AI-powered recommendations, move to Postgres and use `pg_trgm` + GIN indexes or integrate Elasticsearch/Opensearch. Add a `SearchVectorField` (Django contrib.postgres) or create a dedicated document index in ES. Fields to index: `Car.brand`, `Car.model`, `Car.description`, `features.name`, `categories.name`.

6) Unique constraints on Social/Auth models
   - We saw issues with multiple SocialApp entries. Ensure `allauth` SocialApp is unique per (provider, sites) pair. We added dedupe tooling; also add a DB unique constraint if the schema allows it (or enforce in admin).

7) Audit logs & history
   - Add `django-simple-history` or `django-reversion` for critical models (Car, Application, MultiCart, Order models). This helps admin rollback and audit.

8) Query performance & aggregation
   - Ensure aggregation usage uses `annotate` with `F`/`Sum` expressions (Cart totals) to make queries run in DB where possible.

9) Denormalization & caching
   - For high-traffic metrics (views_count, inquiry_count, stats) update counters using Redis counters + periodic writes to DB, or use atomic DB increments with `F()` to avoid race conditions.

10) Media & thumbnails
   - Profile and Car images store derived thumbnails in ImageFields (profile_image_small/medium). Consider moving to a dedicated storage service (S3) and generating thumbnails asynchronously via background worker (Celery/RQ). This avoids slowness on profile save.

11) Constraints & validation
   - Add DB-level constraints for `Car.vin` length and unique VINs when appropriate. Add check constraints for price >= 0.

12) Index missing for `SearchQuery` and `UserCarView`
   - Add indexes on `SearchQuery.query` (or better offload to text index) and `UserCarView.car` + `user` for performance.

13) Consider composite indexes for common filter combos
   - e.g., `(status, created_at)` for Car listing queries.

Model-by-model summary (concise)
--------------------------------
- users.CustomUser
  - Primary user model. Email is USERNAME_FIELD.
  - Recommendations: index email if not already unique (it's unique), ensure username uniqueness is enforced correctly.

- users.Profile
  - OneToOne with CustomUser. Stores thumbnails and approvals. Thumbnails generated synchronously with Pillow; consider async.

- users.ProfileImage
  - Gallery model. Index on `profile` (FK) recommended; meta ordering by `-is_primary, -uploaded_at` is fine.

- users.Application
  - Applicant applications for seller/pilot roles. Consider `status` index for admin review filtering.

- users.Conversation & users.Message
  - Conversations M2M participants; Message FK -> Conversation. Add index `conversation, created_at` for chat history retrieval.

- cars.Car
  - Very rich model with many fields and indexes already. Good.
  - Consider adding partial indexes for `condition='used'` queries, and `price` range GIN/trigram for fuzzy search.

- cars.CarImage/CarVideo
  - Media models; add index on `car`.

- Cart models
  - `Cart` and `CartItem` exist and provide `total_count()` and `total_price()`. Ensure `CartItem.price` is set at insertion.
  - DB constraints: `unique_together` set; ensure index on `cart_id` exists.

- MultiCart / MultiCartItem
  - Good for multi-app carts; consider using contenttypes FKs for integrity.

Operational notes & next steps
-----------------------------
1. Generate a visual ER diagram (SVG) from DOT file:

   - Ensure Graphviz installed locally, then run:

```powershell
# from project root
dot -Tsvg docs/ER_diagram.dot -o docs/ER_diagram.svg
```

2. Apply DB constraints & indexes with migrations
   - After deciding on new indexes/constraints, add Django migrations and apply them.

3. Add monitoring & slow query logging
   - Enable `django.db.backends` logging in DEBUG or use APM (Sentry, NewRelic) for production.

4. Search & recommendation plan
   - For scale: move to Postgres, enable `pg_trgm` and create GIN indexes on searchable text. For large-scale search & AI recommendations, integrate Elasticsearch/Opensearch.

5. Real-time & chat
   - We scaffolded Channels. Persist `Message` rows in the consumer (call `Message.objects.create(...)`) and add indexing for retrieval. Use Redis channel layer for scaling.

6. Security & data integrity
   - Add tests asserting unique constraints, FK cascade behavior, and migration checks. Add occasional DB maintenance tasks for deduping and index rebuilding.

Acceptance criteria for TODO #3
-------------------------------
- ER diagram and the human-readable report exist (this file and `docs/ER_diagram.dot`).
- Recommendations provided for indexes, denormalization, search, and media handling.

If you want, I can now:
- Create specific migration stubs for recommended indexes (e.g., a migration adding an index on `Car.status`),
- Produce the SVG ER diagram from the DOT (requires graphviz installed locally),
- Start implementing `Message` persistence into `users.Message` from the consumer (requires migrations to be applied and Channels enabled).

Which of those would you like me to do next?