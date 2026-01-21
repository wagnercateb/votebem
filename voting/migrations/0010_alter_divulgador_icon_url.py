
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0009_alter_referencia_title_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='divulgador',
            name='icon_url',
            field=models.URLField(blank=True, max_length=1000, null=True, verbose_name='URL do Ícone/Imagem'),
        ),
    ]
