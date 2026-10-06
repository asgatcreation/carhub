from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

class Command(BaseCommand):
    help = 'De-duplicate SocialApp entries by provider and site. Keeps one app per (provider, site) pair.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted but do not delete.')
        parser.add_argument('--keep-last', action='store_true', help='Keep the most recently created SocialApp instead of the oldest.')
        parser.add_argument('--keep-id', type=int, help='Specify a SocialApp id to always keep (if present in duplicates).')

    def handle(self, *args, **options):
        try:
            from allauth.socialaccount.models import SocialApp
            from django.contrib.sites.models import Site
        except Exception as e:
            raise CommandError(f"Required models not available: {e}")

        dry_run = options['dry_run']
        keep_last = options['keep_last']
        keep_id = options.get('keep_id')

        total_deleted = 0
        self.stdout.write('Scanning SocialApp entries for duplicates...')

        providers = SocialApp.objects.values_list('provider', flat=True).distinct()
        for provider in providers:
            for site in Site.objects.all():
                apps = SocialApp.objects.filter(provider=provider, sites=site).order_by('id')
                if apps.count() <= 1:
                    continue

                # Decide keeper
                if keep_id:
                    keeper = apps.filter(id=keep_id).first()
                    if not keeper:
                        # keep_id not in this group; fall back
                        keeper = apps.last() if keep_last else apps.first()
                else:
                    keeper = apps.last() if keep_last else apps.first()

                to_delete = apps.exclude(id=keeper.id)
                if dry_run:
                    self.stdout.write(f"[DRY RUN] Provider={provider} Site={site.domain}: would delete {[a.id for a in to_delete]}; keep {keeper.id}")
                else:
                    with transaction.atomic():
                        ids = [a.id for a in to_delete]
                        count, _ = to_delete.delete()
                        total_deleted += count
                        self.stdout.write(f"Deleted SocialApp ids {ids} for provider={provider}, site={site.domain}; kept {keeper.id}")

        if dry_run:
            self.stdout.write('Dry run complete. No changes made.')
        else:
            self.stdout.write(self.style.SUCCESS(f'Deduplication complete. Total deleted objects: {total_deleted}'))
