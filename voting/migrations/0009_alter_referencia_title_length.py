from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0008_rename_voting_divu_email_idx_voting_divu_email_2a1af4_idx_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=r"ALTER TABLE `voting_referencias` MODIFY COLUMN `title` varchar(1000) NULL;",
            reverse_sql=r"ALTER TABLE `voting_referencias` MODIFY COLUMN `title` varchar(255) NULL;",
        ),
    ]

