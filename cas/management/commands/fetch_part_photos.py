"""Collect freely licensed product-photo candidates from Wikimedia Commons.

    python manage.py fetch_part_photos --out candidates.json

For every photo type in `cas/seed/catalog.py` this searches Commons, keeps CC BY / CC BY-SA /
CC0 / public-domain bitmaps at least 600 px wide, and records author + licence for attribution.
The committed `cas/seed/part_photos.json` was then curated by hand from these candidates
(photos of the wrong kind of part, bicycles, people or logos removed).
"""
import json
import re
import time
from html import unescape

import requests
from django.core.management.base import BaseCommand

from cas.seed.catalog import PHOTO_QUERIES

API = 'https://commons.wikimedia.org/w/api.php'
OK_LICENSES = ('CC BY', 'CC0', 'Public domain', 'PD')
SKIP = re.compile(r'bicycle|bike|v-brake|cantilever|shimano|motorcycle|scooter|train|locomotive|aircraft|logo|diagram|'
                  r'svg|map|museum|poster|advert|chart|graph|tank|tractor|lorry|bus\b', re.I)


def _text(html):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', html or ''))).strip()


def _get(session, params, tries=5):
    """Commons throttles bursts: back off and retry on errors or non-JSON replies."""
    for attempt in range(tries):
        try:
            resp = session.get(API, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
        except (requests.RequestException, ValueError):
            pass
        time.sleep(5 * (attempt + 1))
    return {}


class Command(BaseCommand):
    help = 'Fetch candidate product photos from Wikimedia Commons.'

    def add_arguments(self, parser):
        parser.add_argument('--out', required=True)
        parser.add_argument('--per-query', type=int, default=10)

    def handle(self, *args, **opts):
        session = requests.Session()
        session.headers['User-Agent'] = 'CarHubPortfolioDemo/1.0 (portfolio demo seed script) python-requests'
        try:
            with open(opts['out'], encoding='utf-8') as fh:
                result = json.load(fh)  # resumable
        except (OSError, ValueError):
            result = {}
        for kind, queries in PHOTO_QUERIES.items():
            if result.get(kind):
                continue
            seen, found = set(), []
            for q in queries:
                data = _get(session, {
                    'action': 'query', 'generator': 'search', 'gsrsearch': f'{q} filetype:bitmap', 'gsrnamespace': 6,
                    'gsrlimit': opts['per_query'], 'prop': 'imageinfo', 'iiprop': 'url|extmetadata|size',
                    'iiurlwidth': 1000, 'format': 'json'})
                pages = sorted((data.get('query') or {}).get('pages', {}).values(), key=lambda p: p.get('index', 0))
                for page in pages:
                    title = page['title']
                    if title in seen or SKIP.search(title):
                        continue
                    seen.add(title)
                    info = page['imageinfo'][0]
                    meta = info.get('extmetadata', {})
                    lic = meta.get('LicenseShortName', {}).get('value', '')
                    if not lic.startswith(OK_LICENSES) or info.get('width', 0) < 600:
                        continue
                    found.append({
                        'title': title, 'url': info.get('thumburl') or info['url'],
                        'source': info['descriptionurl'], 'license': lic,
                        'author': _text(meta.get('Artist', {}).get('value', ''))[:120] or 'Unknown',
                        'w': info['width'], 'h': info['height'],
                    })
                time.sleep(1.5)
            result[kind] = found
            self.stdout.write(f'{kind:14} {len(found)} candidates')
            with open(opts['out'], 'w', encoding='utf-8') as fh:
                json.dump(result, fh, indent=1, ensure_ascii=False)
