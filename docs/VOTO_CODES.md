# Códigos de voto (`CongressmanVote.voto`)

Este documento descreve os códigos numéricos utilizados no campo `voto` do modelo `CongressmanVote`, sua semântica e o racional de design adotado no sistema.

## Tabela de códigos

- `-1` — "Não": voto contrário.
- `0`  — "Abstenção": abstenção formal (sem posicionamento por "Sim" ou "Não").
- `1`  — "Sim": voto favorável.
- `2`  — "Dummy": registro artificial, usado em casos de fallback/inserções sintéticas, quando é necessário manter integridade referencial ou sinalizar ausência de dados reais.
- `3`  — "Não Compareceu": ausência/indisponibilidade nos dados oficiais (ex.: não registrado, desconhecido, ausente).
- `4`  — "Abstenção (Art. 17)": abstenção obrigatória do presidente, registrada em payloads oficiais como "Artigo 17"/"Art. 17".

## Motivação e contexto

- O campo `voto` agora é `NOT NULL` no banco. Para acomodar cenários sem voto real e evitar `NULL`, adotamos sentinelas explícitas:
  - `2` para "Dummy" (inserções artificiais),
  - `3` para "Não Compareceu" (ausência/desconhecido dos dados oficiais).
- Essa mudança elimina ambiguidade de `NULL` e simplifica comparações e agregações, mantendo semântica estável e previsível.

## Comportamento no código

- Modelos: `django_votebem/voting/models.py`
  - `VOTO_CHOICES` define os rótulos dos códigos conforme a tabela acima.
  - `default` do campo `voto` aponta para `3` ("Não Compareceu") para evitar `NULL`s em inserções sem especificação.

- Importador oficial: `django_votebem/voting/admin_views.py`
  - Função de mapeamento: valores desconhecidos/ausentes (`tipoVoto` da Câmara) mapeiam para `3` ("Não Compareceu").
  - Inserções dummy (fallbacks sintéticos) usam `2` ("Dummy").
  - Caso especial: `tipoVoto` igual a `"Artigo 17"` ou `"Art. 17"` mapeia para `4` (abstenção Art. 17).

- Comparações de votos: `django_votebem/voting/views.py`
  - Somente valores reais de voto (`-1`, `0`, `1`) são considerados em igualdade entre voto do usuário e voto do congressista.
  - Sentinelas (`2` "Dummy" e `3` "Não Compareceu") são ignoradas em comparações de mérito.

## Migração de dados

- Migração: `0021_congressmanvote_voto_codes_data_fix`
  - Converte registros existentes com `voto=2` para `voto=3` quando o congressista não é dummy (ex.: `id_cadastro != -1`).
  - Mantém `voto=2` para registros explicitamente sintéticos/dummy.

## Boas práticas

- Ao inserir votos reais, sempre usar `-1`, `0` ou `1`.
- Para ausências/desconhecidos derivados de fontes oficiais, usar `3`.
- Para placeholders ou registros artificiais necessários à integridade, usar `2` e documentar o motivo no contexto de inserção.
- Em lógicas de comparação, filtrar exclusivamente por `-1`, `0`, `1` quando a intenção for comparar posicionamentos.
  - Observação: por padrão, `4` (Art. 17) não é incluído nas comparações de mérito. Se desejar tratá-lo como equivalente a `0` (abstenção), podemos ajustar a lógica para considerar `4` como abstenção estendida nas comparações.

## Referências

- Modelo e choices: `voting/models.py`
- Importação e mapeamento: `voting/admin_views.py`
- Lógicas de comparação: `voting/views.py`
- Migrações relacionadas: `0020_alter_congressmanvote_voto`, `0021_congressmanvote_voto_codes_data_fix`, `0022_merge*`, `0023_merge`

## Nota Regimental

Segundo o Regimento Interno da Câmara dos Deputados, "Art. 17" é usado para registrar a abstenção obrigatória do presidente em determinadas situações. No sistema, essa ocorrência é representada pelo código `4` e é mapeada a partir do campo `tipoVoto` dos dados oficiais quando aparece como `"Artigo 17"`/`"Art. 17"`.