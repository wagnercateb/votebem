from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('voting', '0005_create_divulgadores'),
    ]

    operations = [
        migrations.RunSQL(
            sql=r"""
                CREATE TABLE IF NOT EXISTS `voting_referencias_new` (
                  `id` int NOT NULL AUTO_INCREMENT,
                  `proposicao_votacao_id` int NOT NULL,
                  `url` varchar(500) NOT NULL,
                  `kind` varchar(20) NOT NULL,
                  `divulgador_id` int NULL,
                  `title` varchar(255) NULL,
                  `votacao_votebem_id` int NULL,
                  `created_at` datetime(6) NOT NULL,
                  `updated_at` datetime(6) NOT NULL,
                  PRIMARY KEY (`id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            reverse_sql=r"DROP TABLE IF EXISTS `voting_referencias_new`;"
        ),
        migrations.RunSQL(
            sql=r"""
                INSERT INTO `voting_referencias_new` (`id`, `proposicao_votacao_id`, `url`, `kind`, `created_at`, `updated_at`)
                SELECT `id`, `proposicao_votacao_id`, `url`, `kind`, `created_at`, `updated_at`
                FROM `voting_referencias`;
            """,
            reverse_sql=r""
        ),
        migrations.RunSQL(
            sql=r"DROP TABLE `voting_referencias`;",
            reverse_sql=r""
        ),
        migrations.RunSQL(
            sql=r"RENAME TABLE `voting_referencias_new` TO `voting_referencias`;",
            reverse_sql=r""
        ),
        migrations.RunSQL(
            sql=r"CREATE INDEX `voting_ref_kind_idx` ON `voting_referencias` (`kind`);",
            reverse_sql=r"DROP INDEX `voting_ref_kind_idx` ON `voting_referencias`;"
        ),
        migrations.RunSQL(
            sql=r"CREATE INDEX `voting_ref_pv_idx` ON `voting_referencias` (`proposicao_votacao_id`);",
            reverse_sql=r"DROP INDEX `voting_ref_pv_idx` ON `voting_referencias`;"
        ),
        migrations.RunSQL(
            sql=r"CREATE INDEX `voting_ref_divulgador_idx` ON `voting_referencias` (`divulgador_id`);",
            reverse_sql=r"DROP INDEX `voting_ref_divulgador_idx` ON `voting_referencias`;"
        ),
        migrations.RunSQL(
            sql=r"CREATE INDEX `voting_ref_vv_idx` ON `voting_referencias` (`votacao_votebem_id`);",
            reverse_sql=r"DROP INDEX `voting_ref_vv_idx` ON `voting_referencias`;"
        ),
    ]
