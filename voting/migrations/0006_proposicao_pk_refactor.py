from django.db import migrations, models
from django.db.models import F


def fill_tmp_proposicao_ids(apps, schema_editor):
    """Populate temporary proposicao_tmp fields with id_proposicao values,
    using the existing ForeignKey (which points to the old AutoField id).
    """
    Proposicao = apps.get_model('voting', 'Proposicao')
    ProposicaoVotacao = apps.get_model('voting', 'ProposicaoVotacao')
    VotacaoDisponivel = apps.get_model('voting', 'VotacaoDisponivel')
    CongressmanVote = apps.get_model('voting', 'CongressmanVote')

    for Model in (ProposicaoVotacao, VotacaoDisponivel, CongressmanVote):
        for obj in Model.objects.all().iterator():
            # At this stage, obj.proposicao_id refers to Proposicao.id (AutoField)
            if obj.proposicao_id is None:
                continue
            p = Proposicao.objects.filter(id=obj.proposicao_id).only('id_proposicao').first()
            if p:
                obj.proposicao_tmp = p.id_proposicao
                obj.save(update_fields=['proposicao_tmp'])


def transfer_tmp_to_new_fk(apps, schema_editor):
    """After adding new ForeignKeys to id_proposicao, transfer the tmp IDs
    into the new FK columns (named proposicao_new), then the tmp fields will be dropped.
    """
    ProposicaoVotacao = apps.get_model('voting', 'ProposicaoVotacao')
    VotacaoDisponivel = apps.get_model('voting', 'VotacaoDisponivel')
    CongressmanVote = apps.get_model('voting', 'CongressmanVote')

    for Model in (ProposicaoVotacao, VotacaoDisponivel, CongressmanVote):
        # Assign the foreign key by setting the underlying _id field
        Model.objects.filter(proposicao_tmp__isnull=False).update(proposicao_new_id=F('proposicao_tmp'))


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0005_proposicaovotacao'),
    ]

    operations = [
        # 1) Add temporary integer fields to hold id_proposicao values
        migrations.AddField(
            model_name='proposicaovotacao',
            name='proposicao_tmp',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='votacaodisponivel',
            name='proposicao_tmp',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='congressmanvote',
            name='proposicao_tmp',
            field=models.IntegerField(null=True),
        ),

        # 2) Populate tmp fields from existing relations
        migrations.RunPython(fill_tmp_proposicao_ids, migrations.RunPython.noop),

        # 3) Add parallel FK fields (proposicao_new) pointing to id_proposicao
        migrations.AddField(
            model_name='proposicaovotacao',
            name='proposicao_new',
            field=models.ForeignKey(
                to='voting.proposicao',
                to_field='id_proposicao',
                on_delete=models.deletion.CASCADE,
                null=True,
                related_name='+',
                verbose_name='Proposição (nova)'
            ),
        ),
        migrations.AddField(
            model_name='votacaodisponivel',
            name='proposicao_new',
            field=models.ForeignKey(
                to='voting.proposicao',
                to_field='id_proposicao',
                on_delete=models.deletion.CASCADE,
                null=True,
                related_name='+',
                verbose_name='Proposição (nova)'
            ),
        ),
        migrations.AddField(
            model_name='congressmanvote',
            name='proposicao_new',
            field=models.ForeignKey(
                to='voting.proposicao',
                to_field='id_proposicao',
                on_delete=models.deletion.CASCADE,
                null=True,
                related_name='+',
                verbose_name='Proposição (nova)'
            ),
        ),

        # 4) Transfer tmp values into the new FK fields
        migrations.RunPython(transfer_tmp_to_new_fk, migrations.RunPython.noop),

        # 5) Drop unique_together and old FK fields
        migrations.AlterUniqueTogether(
            name='proposicaovotacao',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='proposicaovotacao',
            name='proposicao',
        ),
        migrations.RemoveField(
            model_name='votacaodisponivel',
            name='proposicao',
        ),
        migrations.AlterUniqueTogether(
            name='congressmanvote',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='congressmanvote',
            name='proposicao',
        ),

        # 6) Rename new FK fields to the canonical name 'proposicao'
        migrations.RenameField(
            model_name='proposicaovotacao',
            old_name='proposicao_new',
            new_name='proposicao',
        ),
        migrations.RenameField(
            model_name='votacaodisponivel',
            old_name='proposicao_new',
            new_name='proposicao',
        ),
        migrations.RenameField(
            model_name='congressmanvote',
            old_name='proposicao_new',
            new_name='proposicao',
        ),

        # 7) Restore unique_together constraints
        migrations.AlterUniqueTogether(
            name='proposicaovotacao',
            unique_together={('proposicao', 'votacao_sufixo')},
        ),
        migrations.AlterUniqueTogether(
            name='congressmanvote',
            unique_together={('congressman', 'proposicao')},
        ),

        # 8) Drop tmp fields
        migrations.RemoveField(
            model_name='proposicaovotacao',
            name='proposicao_tmp',
        ),
        migrations.RemoveField(
            model_name='votacaodisponivel',
            name='proposicao_tmp',
        ),
        migrations.RemoveField(
            model_name='congressmanvote',
            name='proposicao_tmp',
        ),

        # 9) Finally, make id_proposicao the primary key and drop the implicit 'id'
        migrations.AlterField(
            model_name='proposicao',
            name='id_proposicao',
            field=models.IntegerField(primary_key=True, serialize=False, verbose_name='ID da Proposição'),
        ),
        migrations.RemoveField(
            model_name='proposicao',
            name='id',
        ),
    ]