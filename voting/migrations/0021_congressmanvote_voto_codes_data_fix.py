from django.db import migrations


def convert_non_dummy_absence(apps, schema_editor):
    CongressmanVote = apps.get_model('voting', 'CongressmanVote')
    Congressman = apps.get_model('voting', 'Congressman')
    # Convert any legacy records with voto=2 that are NOT dummy congressmen (id_cadastro != -1)
    # to voto=3 (Não Compareceu). Dummy remains as voto=2.
    qs = CongressmanVote.objects.filter(voto=2)
    for cv in qs.select_related('congressman'):
        try:
            cm = cv.congressman
            if cm and getattr(cm, 'id_cadastro', None) != -1:
                cv.voto = 3
                cv.save(update_fields=['voto'])
        except Exception:
            # Best effort; skip on any unexpected relation issues
            pass


class Migration(migrations.Migration):
    dependencies = [
        ('voting', '0019_proposicao_data_apresentacao_alter_voto_voto'),
    ]

    operations = [
        migrations.RunPython(convert_non_dummy_absence, migrations.RunPython.noop),
    ]