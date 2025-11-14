# Temas de Proposições

Este documento descreve a nova tabela `voting_temas` e a origem dos dados.

## Tabela

- Nome da tabela: `voting_temas`
- Campos:
  - `codigo` (int): código do tema conforme referência oficial.
  - `nome` (text): nome do tema.
  - `descricao` (text): descrição do tema (pode vir vazio).

## Fonte dos Dados

- Endpoint oficial: `https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTema`
- Foi criada uma migração de dados (`voting/ migrations/0014_populate_temas.py`) que popula a tabela com a lista atual de temas.

## Observações

- A migração utiliza `update_or_create` para evitar duplicidade caso seja executada mais de uma vez.
- O campo `codigo` é indexado para facilitar consultas futuras.