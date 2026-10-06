from django.core.management.base import BaseCommand
from users.models import Conversation, Profile


class Command(BaseCommand):
    help = 'Backfill Profile.responses_count and avg_response_seconds from Conversation messages history.'

    def handle(self, *args, **options):
        self.stdout.write('Starting backfill of response stats...')
        # accumulate stats per profile id
        stats = {}
        qs = Conversation.objects.prefetch_related('messages__sender').all()
        total_convos = qs.count()
        self.stdout.write(f'Processing {total_convos} conversations...')
        for i, convo in enumerate(qs, start=1):
            # order messages by created_at
            msgs = list(convo.messages.order_by('created_at').select_related('sender'))

            # track which (replier_id, other_id) pairs we've already counted
            counted_pairs = set()

            for idx, m in enumerate(msgs):
                # find the most recent previous message by someone else
                prev = None
                for p in reversed(msgs[:idx]):
                    if p.sender_id != m.sender_id:
                        prev = p
                        break
                if not prev:
                    continue

                replier_id = m.sender_id
                other_id = prev.sender_id

                pair = (replier_id, other_id)
                if pair in counted_pairs:
                    # already counted a reply from replier -> other in this convo
                    continue

                # mark as counted and add to stats
                counted_pairs.add(pair)

                try:
                    pid = m.sender.profile.id
                except Exception:
                    continue

                delta = int((m.created_at - prev.created_at).total_seconds()) if m.created_at and prev.created_at else 0
                entry = stats.setdefault(pid, {'count': 0, 'total_seconds': 0})
                entry['count'] += 1
                entry['total_seconds'] += max(0, delta)

            if i % 100 == 0:
                self.stdout.write(f'Processed {i}/{total_convos} conversations...')

        # Apply stats to profiles
        self.stdout.write(f'Updating {len(stats)} profiles...')
        for pid, data in stats.items():
            try:
                prof = Profile.objects.get(pk=pid)
                prof.responses_count = data['count']
                prof.avg_response_seconds = int(round(data['total_seconds'] / data['count'])) if data['count'] else 0
                prof.save(update_fields=['responses_count', 'avg_response_seconds'])
                self.stdout.write(f'Updated profile {prof.user.email}: responses={prof.responses_count}, avg_s={prof.avg_response_seconds}')
            except Profile.DoesNotExist:
                continue

        self.stdout.write('Backfill complete.')
