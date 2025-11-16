# Camara API: Optional Limits

This project’s `CamaraAPIService` now supports optional parameters to reduce fetch size and respect UI-provided limits without breaking existing callers.

- `get_proposicoes_by_date_range(data_inicio, data_fim, ordem="ASC", ordenar_por="id", limit=None, itens_por_pagina=None)`
  - `limit`: caps the total number of propositions returned. Pagination stops early when reached.
  - `itens_por_pagina`: sets the API page size (`itens`). Defaults to `100` for backward compatibility.

- `get_recent_proposicoes(days=7, limit=None, itens_por_pagina=None)`
  - Forwards `limit` and `itens_por_pagina` to `get_proposicoes_by_date_range`.

Admin action `atualizarNProposicoes` was updated to request `limit=n_proposicoes` so the service fetches only what is needed, removing the need to slice locally and shortening the loop.

Existing usages without the new parameters remain unchanged because defaults preserve previous behavior.