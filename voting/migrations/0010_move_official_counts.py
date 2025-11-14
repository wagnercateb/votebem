from django.db import migrations, models

def copy_counts_to_proposicao_votacao(apps, schema_editor):
    # Move existing counts from VotacaoDisponivel to related ProposicaoVotacao
    VotacaoDisponivel = apps.get_model('voting', 'VotacaoDisponivel')
    ProposicaoVotacao = apps.get_model('voting', 'ProposicaoVotacao')
    for vd in VotacaoDisponivel.objects.select_related('proposicao_votacao').all():
        pv = getattr(vd, 'proposicao_votacao', None)
        if pv:
            # Some old rows may not have fields yet depending on migration order; guard with hasattr
            try:
                pv.sim_oficial = getattr(vd, 'sim_oficial', 0) or 0
                pv.nao_oficial = getattr(vd, 'nao_oficial', 0) or 0
                pv.save(update_fields=['sim_oficial', 'nao_oficial'])
            except Exception:
                # Best-effort: ignore rows that fail
                pass

class Migration(migrations.Migration):
    dependencies = [
        ('voting', '0009_proposicaovotacao_prioridade'),
    ]

    operations = [
        # Add fields to ProposicaoVotacao
        migrations.AddField(
            model_name='proposicaovotacao',
            name='sim_oficial',
            field=models.IntegerField(default=0, verbose_name='Votos SIM Oficiais'),
        ),
        migrations.AddField(
            model_name='proposicaovotacao',
            name='nao_oficial',
            field=models.IntegerField(default=0, verbose_name='Votos NÃO Oficiais'),
        ),
        # Copy existing data from VotacaoDisponivel into ProposicaoVotacao
        migrations.RunPython(copy_counts_to_proposicao_votacao, migrations.RunPython.noop),
        # Remove fields from VotacaoDisponivel
        migrations.RemoveField(
            model_name='votacaodisponivel',
            name='sim_oficial',
        ),
        migrations.RemoveField(
            model_name='votacaodisponivel',
            name='nao_oficial',
        ),
    ]