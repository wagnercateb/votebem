# Proposição ⇄ Tema (N:N)

Este documento descreve a tabela `voting_proposicao_tema` e o processo de atualização de temas por proposição.

## Tabelas

- `voting_proposicao` (modelo `Proposicao`)
  - PK: `id_proposicao` (int)
- `voting_temas` (modelo `Tema`)
  - PK lógico: `codigo` (int, `unique=True`)
- `voting_proposicao_tema` (modelo `ProposicaoTema`)
  - `proposicao_id` → FK para `Proposicao(id_proposicao)`
  - `tema_id` → FK para `Tema(codigo)`
  - `unique_together`: (`proposicao`, `tema`)

## Atualização via Painel

- Botão: "Atualizar temas de proposições" em `admin/voting/admin_dashboard.html`.
- Rota: `gerencial:proposicoes_atualizar_temas` → `voting/admin_views.py`.
- Fluxo:
  1. Seleciona proposições sem vínculos na `voting_proposicao_tema`.
  2. Para cada proposição, faz `GET` em `https://dadosabertos.camara.leg.br/api/v2/proposicoes/<id>/temas`.
  3. Para cada item em `dados`, lê `codTema` e cria vínculo (`proposicao_id`, `tema_id=codigo`).
- Resultado: mensagem de sucesso com total processado e vínculos criados.

## Observações

- `Tema.codigo` é único para permitir FK por código (via `to_field`).
- O processo ignora códigos de tema que não existirem em `voting_temas`.
- Reexecuções não criam duplicados por causa de `get_or_create` e `unique_together`.