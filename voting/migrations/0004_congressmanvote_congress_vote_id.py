from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0003_congressman_partidos_historico'),
    ]

    operations = [
        migrations.AddField(
            model_name='congressmanvote',
            name='congress_vote_id',
            field=models.IntegerField(blank=True, null=True, verbose_name='ID Votação da Câmara'),
        ),
    ]