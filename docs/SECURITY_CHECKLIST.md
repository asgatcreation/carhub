Security & Production Checklist
===============================

Quick checklist for production readiness.

1. Secrets
   - Move `SECRET_KEY` and all provider secrets into environment variables or a vault.
   - Use `python-dotenv` only for local development.

2. HTTPS & Cookies
   - Set `SECURE_SSL_REDIRECT = True` in production.
   - `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`.
   - Set `SESSION_COOKIE_HTTPONLY = True` and `CSRF_COOKIE_HTTPONLY = False` (CSRF must be readable by browser JS if using certain flows).

3. CORS & Allowed hosts
   - Configure `ALLOWED_HOSTS` precisely.
   - If using APIs, configure `django-cors-headers` appropriately.

4. Content Security Policy (CSP)
   - Implement an appropriate CSP to limit script/style sources.

5. Authentication
   - Enforce strong password policies and 2FA for admin users.
   - Rate-limit auth endpoints and implement login throttling.

6. File uploads
   - Scan uploaded files and limit sizes.
   - Use signed URLs for direct-to-cloud uploads.

7. Database
   - Use managed Postgres for production.
   - Configure daily backups and point-in-time recovery if available.

8. Logging & Monitoring
   - Integrate Sentry or similar for error tracking.
   - Use structured logs and log rotation.

9. Dependencies
   - Pin dependency versions and run `pip-audit` for vulnerabilities.

10. CI/CD
   - Run migrations in a safe deployment step.
   - Use feature flags for major changes.

11. Rate limiting & DDoS
   - Use Cloudflare or WAF and rate limiting for login/add-to-cart endpoints.

12. Secrets rotation & audits
   - Rotate API keys regularly and audit access.

13. Penetration testing
   - Schedule security audits prior to go-live.

