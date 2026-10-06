"""Build `cars/seed/photos.json` from Wikipedia/Wikimedia Commons.

For every model in the seed catalogue this picks the article's lead photo plus
a few more photos whose file names mention the model, keeping only freely
licensed Commons files and recording author + licence for attribution.

Run once (needs internet); the resulting JSON is committed so `seed_demo`
works offline:

    python manage.py fetch_car_photos

The committed photos.json was then curated by hand: photos showing a different
generation than the listing were removed, thin sets were topped up from the
model's Wikimedia Commons category, and interior shots are flagged
(`"interior": true`) so they are never used as a listing's cover photo.
"""
import json
import re
import time
from html import unescape
from pathlib import Path

import requests
from django.core.management.base import BaseCommand

from cars.seed.catalog import MODELS

API = 'https://en.wikipedia.org/w/api.php'
OUT = Path(__file__).resolve().parents[2] / 'seed' / 'photos.json'
SKIP_WORDS = ('engine', 'concept', 'police', 'taxi', 'crash', 'race', 'rally', 'badge', 'emblem', 'logo',
              'prototype', 'chassis', 'cutaway', 'museum', 'wheel', 'motor show', 'autosalon', 'ambulance')
BRAND_WORDS = {'Mercedes-Benz': ['mercedes', 'benz', 'amg'], 'Land Rover': ['range rover', 'land rover'],
               'Volkswagen': ['volkswagen', 'vw']}
MAX_PHOTOS = 4


def _matches(name, words):
    name = name.lower()
    for w in words:
        if len(w) <= 3:
            if re.search(rf'(?<![a-z0-9]){re.escape(w)}(?![a-z])', name):
                return True
        elif w in name:
            return True
    return False


def _photo_year(name):
    m = re.search(r'(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)', name)
    return int(m.group(1)) if m else None


def _year_ok(name, model, generic_article):
    """Reject photos of older generations: the file name's year must fit the listing's year range."""
    year = _photo_year(name)
    if year is None:
        return not generic_article  # undated photos are only trusted on generation-specific articles
    return year >= model['years'][0] - 1


def _strip_html(value):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', value or ''))).strip()


class Command(BaseCommand):
    help = 'Fetch freely licensed car photos for the demo catalogue (writes cars/seed/photos.json).'

    def add_arguments(self, parser):
        parser.add_argument('--refresh', action='store_true', help='Ignore previously fetched photos.')

    def handle(self, *args, **options):
        session = requests.Session()
        session.headers['User-Agent'] = 'CarHubPortfolioDemo/1.0 (https://github.com/; demo marketplace seed script) python-requests'
        # Resumable: keep what earlier runs already fetched
        result = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() and not options['refresh'] else {}
        done = {}
        for m in MODELS:
            cache_key = (m['wiki'], m['years'][0])
            if result.get(m['key']):
                done[cache_key] = result[m['key']]
            if cache_key not in done:
                done[cache_key] = self._photos_for(session, m['wiki'], m)
            result[m['key']] = done[cache_key]
            OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
            photos = result[m['key']]
            status = self.style.SUCCESS if photos else self.style.WARNING
            self.stdout.write(status(f"{m['key']:<10} {len(photos)} photos  ({m['wiki']})"))
        self.stdout.write(self.style.SUCCESS(f'Wrote {OUT}'))

    def _get(self, session, params):
        for attempt in range(12):
            time.sleep(2)  # be polite to the Wikimedia API
            resp = session.get(API, params=params, timeout=30)
            if resp.status_code == 200 and resp.text.startswith('{'):
                return resp.json()
            wait = int(resp.headers.get('Retry-After', 0) or 0) or 60
            self.stdout.write(f'  HTTP {resp.status_code}, waiting {wait}s')
            time.sleep(wait)
        resp.raise_for_status()
        raise RuntimeError('Wikipedia API did not return JSON')

    def _photos_for(self, session, title, model):
        data = self._get(session, {
            'action': 'query', 'titles': title, 'redirects': 1, 'format': 'json',
            'prop': 'pageimages|images', 'piprop': 'name', 'imlimit': 200,
        })
        page = next(iter(data['query']['pages'].values()))
        brand_words = BRAND_WORDS.get(model['brand'], [model['brand'].lower()])

        generic = '(' not in title and not model.get('single_generation')
        candidates = []
        lead = page.get('pageimage')
        if lead and _year_ok(lead, model, generic):
            candidates.append('File:' + lead.replace('_', ' '))
        for img in page.get('images', []):
            name = img['title']
            if not name.lower().endswith(('.jpg', '.jpeg')) or name in candidates:
                continue
            if any(w in name.lower() for w in SKIP_WORDS) or not _year_ok(name, model, generic):
                continue
            if _matches(name, model['kw']) and (_matches(name, brand_words) or len(model['kw'][0]) > 3):
                candidates.append(name)
        if not candidates:
            return []

        info = self._get(session, {
            'action': 'query', 'titles': '|'.join(candidates[:25]), 'format': 'json',
            'prop': 'imageinfo', 'iiprop': 'url|extmetadata', 'iiurlwidth': 1280,
        })
        by_title = {p['title']: p for p in info['query']['pages'].values()}
        normalized = {n['from']: n['to'] for n in info['query'].get('normalized', [])}

        photos = []
        for name in candidates[:25]:
            p = by_title.get(normalized.get(name, name))
            if not p or p.get('imagerepository') != 'shared' or not p.get('imageinfo'):
                continue  # only Commons-hosted (freely licensed) files
            ii = p['imageinfo'][0]
            meta = ii.get('extmetadata', {})
            licence = meta.get('LicenseShortName', {}).get('value', '')
            if not licence or 'fair use' in licence.lower():
                continue
            if ii.get('thumbwidth', 0) < 800:
                continue
            photos.append({
                'url': ii['thumburl'],
                'author': _strip_html(meta.get('Artist', {}).get('value', ''))[:120] or 'Unknown',
                'license': licence,
                'license_url': meta.get('LicenseUrl', {}).get('value', ''),
                'source': ii.get('descriptionurl', ''),
            })
            if len(photos) >= MAX_PHOTOS:
                break
        return photos
