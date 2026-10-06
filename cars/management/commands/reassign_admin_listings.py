from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from cars.models import Car
import csv


class Command(BaseCommand):
    help = (
        "Reassign cars currently owned by a superuser (legacy/admin) to a different user.\n"
        "Supports CSV mapping (slug,user_email) or single target user via --to-email.\n"
        "Run with --dry-run to preview changes. Use --commit to apply."
    )

    def add_arguments(self, parser):
        parser.add_argument('--map-csv', type=str, help='Path to CSV file with columns: slug,user_email')
        parser.add_argument('--to-email', type=str, help='Email of the user to receive all reassigned listings')
        parser.add_argument('--placeholder-email', type=str, help='Create/find a placeholder seller account with this email')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without applying')
        parser.add_argument('--commit', action='store_true', help='Apply changes (must be used intentionally)')

    def handle(self, *args, **options):
        User = get_user_model()
        map_csv = options.get('map_csv')
        to_email = options.get('to_email')
        placeholder_email = options.get('placeholder_email')
        dry_run = options.get('dry_run')
        do_commit = options.get('commit')

        if not (map_csv or to_email or placeholder_email):
            raise CommandError('Specify --map-csv or --to-email or --placeholder-email')

        admin_cars = Car.objects.filter(created_by__is_superuser=True)
        if not admin_cars.exists():
            self.stdout.write('No cars currently attributed to superuser accounts.')
            return

        # Build mapping: slug -> target_user
        mapping = {}
        if map_csv:
            try:
                with open(map_csv, newline='', encoding='utf-8') as fh:
                    reader = csv.DictReader(fh)
                    if 'slug' not in reader.fieldnames or 'user_email' not in reader.fieldnames:
                        raise CommandError('CSV must include headers: slug,user_email')
                    for row in reader:
                        slug = row.get('slug') and row.get('slug').strip()
                        email = row.get('user_email') and row.get('user_email').strip()
                        if not slug or not email:
                            continue
                        user = User.objects.filter(email__iexact=email).first()
                        if not user:
                            self.stdout.write(self.style.WARNING(f'No user found with email {email}; skipping slug {slug}'))
                            continue
                        mapping[slug] = user
            except FileNotFoundError:
                raise CommandError(f'CSV file not found: {map_csv}')

        target_user = None
        if to_email:
            target_user = User.objects.filter(email__iexact=to_email).first()
            if not target_user:
                raise CommandError(f'No user found with email {to_email}')

        placeholder_user = None
        if placeholder_email:
            placeholder_user, created = User.objects.get_or_create(email=placeholder_email, defaults={'username': placeholder_email.split('@')[0]})
            if created:
                # Set unusable password; admin should review.
                placeholder_user.set_unusable_password()
                placeholder_user.is_active = True
                placeholder_user.save()
                self.stdout.write(self.style.SUCCESS(f'Created placeholder user {placeholder_email}'))

        # Prepare changes list
        changes = []
        for car in admin_cars.select_related('created_by'):
            slug = car.slug
            new_user = None
            if mapping and slug in mapping:
                new_user = mapping[slug]
            elif target_user:
                new_user = target_user
            elif placeholder_user:
                new_user = placeholder_user

            if new_user:
                changes.append((car, car.created_by, new_user))

        if not changes:
            self.stdout.write('No candidate changes found (CSV mapping may not match, or no target user).')
            return

        # Output summary
        self.stdout.write(self.style.NOTICE(f'Found {len(changes)} car(s) to reassign.'))
        for car, old, new in changes:
            self.stdout.write(f'{car.slug}: {old.email if old else None} -> {new.email}')

        if dry_run and not do_commit:
            self.stdout.write(self.style.WARNING('Dry run complete. No changes applied.'))
            return

        if not do_commit:
            raise CommandError('No --commit provided. To apply the changes run again with --commit')

        # Apply changes
        applied = 0
        for car, old, new in changes:
            car.created_by = new
            car.save(update_fields=['created_by'])
            applied += 1

        self.stdout.write(self.style.SUCCESS(f'Applied {applied} changes.'))