"""
Second-stage merge migration to unify duplicate merge heads.

Context:
  - Two merge migrations exist at the same level:
      * 0022_merge
      * 0022_merge_20251123_1122
  - This migration depends on both, producing a single linear head so
    future migrations are unambiguous.

Behavior:
  - No operations; this is purely a dependency merge.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("voting", "0022_merge"),
        ("voting", "0022_merge_20251123_1122"),
    ]

    operations = []