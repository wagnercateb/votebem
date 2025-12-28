from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ('voting', '0004_alter_proposicao_titulo_alter_referencia_kind_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Divulgador',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='E-mail')),
                ('domain_parte', models.CharField(blank=True, max_length=255, null=True, verbose_name='Domínio (parte)')),
                ('alias', models.CharField(blank=True, max_length=255, null=True, verbose_name='Apelido')),
                ('tooltip', models.TextField(blank=True, null=True, verbose_name='Tooltip')),
                ('icon_url', models.URLField(blank=True, null=True, verbose_name='URL do Ícone/Imagem')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'db_table': 'voting_divulgadores',
                'verbose_name': 'Divulgador',
                'verbose_name_plural': 'Divulgadores',
                'ordering': ['alias', 'email'],
            },
        ),
        migrations.AddIndex(
            model_name='divulgador',
            index=models.Index(fields=['email'], name='voting_divu_email_idx'),
        ),
        migrations.AddIndex(
            model_name='divulgador',
            index=models.Index(fields=['domain_parte'], name='voting_divu_domain_idx'),
        ),
    ]
