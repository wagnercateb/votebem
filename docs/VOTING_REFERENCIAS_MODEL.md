# Modelo: voting_referencias

Este documento descreve a nova tabela `voting_referencias`, criada para armazenar referências externas (URLs) relacionadas a votações oficiais de proposições (`voting_proposicaovotacao`).

## Visão Geral

- Tabela: `voting_referencias` (nome fixo via `Meta.db_table`).
- Relação: 1:N com `voting_proposicaovotacao` (uma votação pode ter várias referências).
- Campos principais:
  - `proposicao_votacao`: FK para `ProposicaoVotacao` (obrigatório).
  - `url`: `URLField` (validação básica de URL, tamanho máximo 500).
  - `kind`: `CharField` com `choices` para o tipo da referência.
    - Valores suportados: `web_page`, `sound`, `social_media`.
  - Metadados: `created_at`, `updated_at`.
  - Índices: em `proposicao_votacao` e `kind` para consultas eficientes.

## Implementação

Classe no arquivo `voting/models.py` com comentários explicando objetivo e uso:

```python
class Referencia(models.Model):
    class Kind(models.TextChoices):
        WEB_PAGE = 'web_page', 'Página Web'
        SOUND = 'sound', 'Áudio'
        SOCIAL_MEDIA = 'social_media', 'Rede Social'

    proposicao_votacao = models.ForeignKey(
        'voting.ProposicaoVotacao',
        on_delete=models.CASCADE,
        related_name='referencias',
        verbose_name='Votação da Proposição'
    )

    url = models.URLField(max_length=500, verbose_name='URL da Referência')
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name='Tipo da Referência')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voting_referencias'
        verbose_name = 'Referência de Votação'
        verbose_name_plural = 'Referências de Votação'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['proposicao_votacao']),
            models.Index(fields=['kind']),
        ]
```

## Admin Django

- Foi adicionada uma `TabularInline` (`ReferenciaInline`) ao `ProposicaoVotacaoAdmin` para permitir o gerenciamento de referências diretamente nas páginas de edição de votações oficiais.
- Campos exibidos: `url`, `kind`, `created_at` (somente leitura).

## Migrações

- A migração `0017_alter_proposicaotema_tema_referencia.py` cria a tabela `voting_referencias` e adiciona índices conforme acima.
- Em ambientes com dados já existentes, a aplicação de migrações pode falhar caso haja inconsistências de integridade em tabelas antigas (ex.: `voting_voto` referenciando `voting_votacaovotebem` inexistente).

### Diagnóstico recomendado

- Verifique inconsistências com consultas simples:
  - `SELECT votacao_id FROM voting_voto WHERE votacao_id NOT IN (SELECT id FROM voting_votacaovotebem);`
- Corrija dados inválidos antes de executar `migrate` (ex.: apagar ou atualizar registros órfãos).

### Comandos típicos

```
python manage.py makemigrations voting
python manage.py migrate
```

> Observação: Evite usar `--fake` em criação de tabela, pois não criará a estrutura necessária.

## Uso (exemplos)

### Criar referência

```python
pv = ProposicaoVotacao.objects.get(pk=123)
Referencia.objects.create(
    proposicao_votacao=pv,
    url='https://example.com/materia/123',
    kind=Referencia.Kind.WEB_PAGE
)
```

### Consultar por tipo

```python
refs_web = Referencia.objects.filter(
    proposicao_votacao=pv,
    kind=Referencia.Kind.WEB_PAGE
)
```

### Percorrer em template

```django
{% for ref in proposicao_votacao.referencias.all %}
  <a href="{{ ref.url }}">{{ ref.get_kind_display }}</a>
{% endfor %}
```

## Considerações

- Os tipos (`kind`) são extensíveis; basta adicionar novas opções em `TextChoices`.
- Para URLs muito longas, ajuste o `max_length` conforme necessário.