from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Fix broken foreign keys in voting_congressmanvote by nullifying"
        " references to missing voting_proposicaovotacao rows."
    )

    def handle(self, *args, **options):
        from voting.models import CongressmanVote, ProposicaoVotacao, VotacaoVoteBem

        # Collect existing ProposicaoVotacao IDs
        existing_ids = set(
            ProposicaoVotacao.objects.values_list('id', flat=True)
        )

        # Find congressman votes referencing non-existent ProposicaoVotacao
        broken_qs = CongressmanVote.objects.exclude(
            proposicao_votacao_id__in=existing_ids
        ).exclude(proposicao_votacao_id__isnull=True)

        broken_count = broken_qs.count()

        if broken_count == 0:
            self.stdout.write(self.style.SUCCESS("No broken foreign keys in CongressmanVote."))

        self.stdout.write(
            f"Found {broken_count} CongressmanVote rows with broken FK; nullifying."
        )

        # Nullify invalid foreign keys in a single transaction
        with transaction.atomic():
            broken_qs.update(proposicao_votacao=None)

        self.stdout.write(self.style.SUCCESS("Foreign keys in CongressmanVote fixed."))

        # Fix broken foreign keys in VotacaoVoteBem as well
        broken_vvb_qs = VotacaoVoteBem.objects.exclude(
            proposicao_votacao_id__in=existing_ids
        ).exclude(proposicao_votacao_id__isnull=True)

        broken_vvb_count = broken_vvb_qs.count()
        if broken_vvb_count == 0:
            self.stdout.write(self.style.SUCCESS("No broken foreign keys in VotacaoVoteBem."))
            return

        self.stdout.write(
            f"Found {broken_vvb_count} VotacaoVoteBem rows with broken FK; nullifying."
        )

        with transaction.atomic():
            broken_vvb_qs.update(proposicao_votacao=None)

        self.stdout.write(self.style.SUCCESS("Foreign keys in VotacaoVoteBem fixed."))