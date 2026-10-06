# Developer notes

Setup, demo accounts, payments, real-time chat and tests are documented in [README.md](README.md).

Useful commands:

```bash
python manage.py seed_demo --reset      # rebuild demo data
python manage.py fetch_car_photos       # re-collect photo metadata (needs internet; see docstring)
python manage.py makemigrations --check --dry-run
python manage.py test
```
