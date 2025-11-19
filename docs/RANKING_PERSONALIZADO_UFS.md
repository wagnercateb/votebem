# Ranking Personalizado — Seleção de Estados e Persistência

Este documento descreve como funciona a seleção de estados (UFs) na página de Ranking Personalizado (`/voting/ranking/`) e como ela é persistida entre acessos.

## Seleção de UFs

- O usuário pode selecionar múltiplas UFs (por exemplo, `SP`, `RJ`, `MG`).
- Existe uma opção de “Todos os estados”. Quando selecionada, o ranking considera todos os congressistas ativos.
- A seleção é feita via formulário `GET` com os parâmetros:
  - `ufs`: múltiplos valores de UF (ex.: `ufs=SP&ufs=RJ`)
  - `all=1`: para selecionar todos os estados

## Persistência (Cookies)

- A seleção de estados é persistida em um cookie chamado `ranking_ufs` por até 180 dias.
- Valores possíveis do cookie:
  - `ALL`: quando todos os estados são selecionados
  - Lista separada por vírgula (ex.: `SP,RJ,MG`)
- Prioridade de leitura da seleção:
  1. Parâmetros `GET` explícitos (`ufs`/`all`)
  2. Cookie `ranking_ufs`
  3. UF do perfil do usuário (se existente)

## Paginação

- Os links de paginação mantêm a seleção atual por meio de uma `query string` adicionada às URLs (`current_query`).
  - Ex.: `?page=2&ufs=SP&ufs=RJ` ou `?page=2&all=1`.

## Observações de Implementação

- A view `PersonalizedRankingView` valida UFs contra a lista de UFs brasileiras.
- O cálculo de compatibilidade e a ordenação por `total_score` permanecem os mesmos; apenas o filtro de UFs foi ampliado para múltiplas UFs ou todos os estados.