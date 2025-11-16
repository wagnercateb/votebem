# Generated manually to set 'codigo' as PK and drop 'id' on Tema
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0015_alter_tema_codigo_proposicaotema'),
    ]

    operations = [
        # Primeiro tornamos 'codigo' a chave primária
        migrations.AlterField(
            model_name='tema',
            name='codigo',
            field=models.IntegerField(primary_key=True, serialize=False),
        ),
        # Em seguida removemos o campo 'id' automático
        migrations.RemoveField(
            model_name='tema',
            name='id',
        ),
    ]