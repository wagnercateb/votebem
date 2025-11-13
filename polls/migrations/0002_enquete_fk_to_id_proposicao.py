from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0001_initial'),
        # Do not depend on voting 0006 to allow applying this first
    ]

    operations = [
        migrations.AlterField(
            model_name='enquete',
            name='proposicao',
            field=models.ForeignKey(
                to='voting.proposicao',
                to_field='id_proposicao',
                on_delete=django.db.models.deletion.CASCADE,
                verbose_name='Proposição',
                db_constraint=False,
            ),
        ),
    ]