from django.db import migrations, models


def migrate_voto_char_to_int(apps, schema_editor):
    Voto = apps.get_model('voting', 'Voto')
    for voto in Voto.objects.all():
        val = getattr(voto, 'voto', None)
        mapped = None
        if val == 'SIM':
            mapped = 1
        elif val == 'NAO':
            mapped = -1
        elif val == 'ABSTENCAO':
            mapped = 0
        # Set default to None if unknown
        setattr(voto, 'voto_new', mapped)
        voto.save(update_fields=['voto_new'])


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0017_alter_proposicaotema_tema_referencia'),
    ]

    operations = [
        # Add new peso field
        migrations.AddField(
            model_name='voto',
            name='peso',
            field=models.SmallIntegerField(default=1, verbose_name='Peso'),
        ),
        # Add temporary integer field for voto
        migrations.AddField(
            model_name='voto',
            name='voto_new',
            field=models.IntegerField(null=True, choices=[(1, 'Sim'), (-1, 'Não'), (0, 'Abstenção')], verbose_name='Voto'),
        ),
        migrations.RunPython(migrate_voto_char_to_int, migrations.RunPython.noop),
        # Remove old char field
        migrations.RemoveField(
            model_name='voto',
            name='voto',
        ),
        # Rename new field to voto
        migrations.RenameField(
            model_name='voto',
            old_name='voto_new',
            new_name='voto',
        ),
    ]