# Componente: Barra de Ações da Proposição

Este componente renderiza uma barra reutilizável com três botões relacionados a uma `Proposição`:

- Obter votações da proposição → `/gerencial/?proposicao_id=<id>`
- Votos oficiais (botão dividido com dropdown listando cada `VotacaoVoteBem`) → `/voting/votos/oficiais/?votacao_id=<id>` (tooltip usa `descricao` de `ProposicaoVotacao`)
- Editar votações VoteBem → `/gerencial/votacao/<id>/edit/`

## Uso

1. Carregue a tag no template:

```
{% load voting_components %}
```

2. Insira o componente, preferencialmente próximo ao cabeçalho da página:

```
{% proposicao_action_bar %}
```

3. Opcionalmente, forneça `proposicao_id` explicitamente:

```
{% proposicao_action_bar proposicao_id=2270800 %}
```

## Descoberta automática de `proposicao_id`

A tag tenta identificar `proposicao_id` do contexto nas seguintes fontes, nesta ordem:

- `proposicao.id_proposicao`
- `votacao.proposicao_votacao.proposicao.id_proposicao`
- Primeiro item de `votacoes` → `proposicao_votacao.proposicao.id_proposicao`
- `proposicao_votacao.proposicao_id` ou `proposicao_votacao.proposicao.id_proposicao`
- `pv.proposicao_id` ou `pv.proposicao.id_proposicao`

Se não encontrar, os botões exibem estado desabilitado.

## Observações

- O tooltip dos itens do dropdown “Votos oficiais” usa `ProposicaoVotacao.descricao`; se ausente, cai para `VotacaoVoteBem.titulo`.
- O botão principal “Votos oficiais” navega para o primeiro `votacao_id` disponível; o dropdown lista todos os IDs encontrados.