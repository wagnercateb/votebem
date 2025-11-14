from django.core.management.base import BaseCommand
from django.db import transaction
from voting.models import Voto, VotacaoVoteBem


class Command(BaseCommand):
    help = (
        "Delete orphan Voto rows whose foreign key 'votacao_id' no longer "
        "matches any existing VotacaoVoteBem. Useful before applying migrations "
        "that enforce FK integrity checks."
    )

    def handle(self, *args, **options):
        # Fetch all valid VotacaoVoteBem IDs once
        valid_ids = set(
            VotacaoVoteBem.objects.values_list('id', flat=True)
        )

        # Identify orphan votes by comparing raw FK values
        to_delete_ids = []
        for voto in Voto.objects.only('id', 'votacao_id').iterator():
            if voto.votacao_id not in valid_ids:
                to_delete_ids.append(voto.id)

        if not to_delete_ids:
            self.stdout.write(self.style.SUCCESS('No orphan votes found.'))
            return

        # Delete orphans in a single transaction
        with transaction.atomic():
            deleted, _ = Voto.objects.filter(id__in=to_delete_ids).delete()

        self.stdout.write(
            self.style.WARNING(
                f'Deleted {deleted} orphan Voto rows referencing missing VotacaoVoteBem.'
            )
        )