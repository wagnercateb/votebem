from django.db import migrations


def seed_temas(apps, schema_editor):
    """
    Populate the 'voting_temas' table with the reference data from
    Câmara dos Deputados API codTema list.

    Source:
    https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTema
    """
    Tema = apps.get_model('voting', 'Tema')

    dados = [
        {"cod": "34", "nome": "Administração Pública", "descricao": ""},
        {"cod": "35", "nome": "Arte, Cultura e Religião", "descricao": ""},
        {"cod": "37", "nome": "Comunicações", "descricao": ""},
        {"cod": "39", "nome": "Esporte e Lazer", "descricao": ""},
        {"cod": "40", "nome": "Economia", "descricao": ""},
        {"cod": "41", "nome": "Cidades e Desenvolvimento Urbano", "descricao": ""},
        {"cod": "42", "nome": "Direito Civil e Processual Civil", "descricao": ""},
        {"cod": "43", "nome": "Direito Penal e Processual Penal", "descricao": ""},
        {"cod": "44", "nome": "Direitos Humanos e Minorias", "descricao": ""},
        {"cod": "46", "nome": "Educação", "descricao": ""},
        {"cod": "48", "nome": "Meio Ambiente e Desenvolvimento Sustentável", "descricao": ""},
        {"cod": "51", "nome": "Estrutura Fundiária", "descricao": ""},
        {"cod": "52", "nome": "Previdência e Assistência Social", "descricao": ""},
        {"cod": "53", "nome": "Processo Legislativo e Atuação Parlamentar", "descricao": ""},
        {"cod": "54", "nome": "Energia, Recursos Hídricos e Minerais", "descricao": ""},
        {"cod": "55", "nome": "Relações Internacionais e Comércio Exterior", "descricao": ""},
        {"cod": "56", "nome": "Saúde", "descricao": ""},
        {"cod": "57", "nome": "Defesa e Segurança", "descricao": ""},
        {"cod": "58", "nome": "Trabalho e Emprego", "descricao": ""},
        {"cod": "60", "nome": "Turismo", "descricao": ""},
        {"cod": "61", "nome": "Viação, Transporte e Mobilidade", "descricao": ""},
        {"cod": "62", "nome": "Ciência, Tecnologia e Inovação", "descricao": ""},
        {"cod": "64", "nome": "Agricultura, Pecuária, Pesca e Extrativismo", "descricao": ""},
        {"cod": "66", "nome": "Indústria, Comércio e Serviços", "descricao": ""},
        {"cod": "67", "nome": "Direito e Defesa do Consumidor", "descricao": ""},
        {"cod": "68", "nome": "Direito Constitucional", "descricao": ""},
        {"cod": "70", "nome": "Finanças Públicas e Orçamento", "descricao": ""},
        {"cod": "72", "nome": "Homenagens e Datas Comemorativas", "descricao": ""},
        {"cod": "74", "nome": "Política, Partidos e Eleições", "descricao": ""},
        {"cod": "76", "nome": "Direito e Justiça", "descricao": ""},
        {"cod": "85", "nome": "Ciências Exatas e da Terra", "descricao": ""},
        {"cod": "86", "nome": "Ciências Sociais e Humanas", "descricao": ""},
    ]

    # Upsert-like behavior: avoid duplicates if run multiple times
    for item in dados:
        codigo_int = int(item["cod"]) if isinstance(item["cod"], str) else item["cod"]
        Tema.objects.update_or_create(
            codigo=codigo_int,
            defaults={
                "nome": item["nome"],
                "descricao": item.get("descricao", "") or "",
            },
        )


def unseed_temas(apps, schema_editor):
    """Rollback helper: remove all seeded temas."""
    Tema = apps.get_model('voting', 'Tema')
    Tema.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('voting', '0013_tema'),
    ]

    operations = [
        migrations.RunPython(seed_temas, reverse_code=unseed_temas),
    ]