"""
Merge migration to resolve divergent branches in the `voting` app.

This file explicitly merges the branches:
  - 0020_alter_congressmanvote_voto (schema change making `voto` NOT NULL
    and updating choices)
  - 0021_congressmanvote_voto_codes_data_fix (data migration converting
    existing `voto=2` rows to `voto=3` for non-dummy congressmen)

Rationale:
  - The project now uses explicit numeric codes for `CongressmanVote.voto`:
      -1 => "Não"
       0 => "Abstenção"
       1 => "Sim"
       2 => "Dummy" (records artificially inserted for placeholders/fallbacks)
       3 => "Não Compareceu" (absence/unknown from official data)
  - The schema change and the data migration target different concerns
    (schema vs. data), and do not conflict. This merge marks them as
    siblings and produces a unified migration history for Django.

Note:
  - This migration contains no operations; it only provides a combined
    dependency so Django recognizes a single linear history moving forward.
"""

from django.db import migrations


class Migration(migrations.Migration):
    # Merge the two branches by depending on both; no operations required.
    dependencies = [
        ("voting", "0020_alter_congressmanvote_voto"),
        ("voting", "0021_congressmanvote_voto_codes_data_fix"),
    ]

    operations = []