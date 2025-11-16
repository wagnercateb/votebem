"""
Management command to remove rows in `voting_voto` that reference
non-existent `voting_votacaovotebem` IDs.

This fixes IntegrityError during migrations on SQLite when legacy or
inconsistent data remains in the `Voto` table.

Usage:
  - Preview only:  `python manage.py cleanup_invalid_votos --dry-run`
  - Apply cleanup: `python manage.py cleanup_invalid_votos`

Notes:
  - The command runs inside a transaction and prints a summary.
  - It only deletes `Voto` rows whose `votacao_id` does not exist in
    `VotacaoVoteBem`.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from voting.models import Voto, VotacaoVoteBem


class Command(BaseCommand):
    help = (
        "Remove Voto rows with invalid foreign key to VotacaoVoteBem. "
        "Use --dry-run to preview without deleting."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report invalid rows; do not delete.",
        )

    def handle(self, *args, **opts):
        # Collect distinct votacao_id values in Voto
        votacao_ids = list(
            Voto.objects.values_list("votacao_id", flat=True).distinct()
        )

        # Determine which IDs do not exist in VotacaoVoteBem
        existing_ids = set(
            VotacaoVoteBem.objects.filter(id__in=votacao_ids).values_list(
                "id", flat=True
            )
        )
        invalid_ids = [vid for vid in votacao_ids if vid not in existing_ids]

        # Count how many rows would be deleted
        total_invalid_rows = Voto.objects.filter(
            votacao_id__in=invalid_ids
        ).count()

        self.stdout.write(
            f"Found {total_invalid_rows} invalid Voto rows. "
            f"Broken votacao_id values: {invalid_ids}"
        )

        if opts.get("dry_run"):
            self.stdout.write("Dry run; no changes made.")
            return

        if total_invalid_rows == 0:
            self.stdout.write("No invalid rows found; nothing to do.")
            return

        # Delete invalid rows inside a transaction
        with transaction.atomic():
            deleted_count, _ = Voto.objects.filter(
                votacao_id__in=invalid_ids
            ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} invalid Voto rows successfully."
            )
        )