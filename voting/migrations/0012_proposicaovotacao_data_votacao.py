from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0011_votacaovotebem_alter_voto_votacao_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposicaovotacao',
            name='data_votacao',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Data/Hora do Registro da Votação'),
        ),
    ]