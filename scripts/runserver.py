"""`manage.py runserver` on the port given by $PORT (default 8000), used by the editor preview."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.management import execute_from_command_line  # noqa: E402

execute_from_command_line(['manage.py', 'runserver', os.environ.get('PORT', '8000')])
