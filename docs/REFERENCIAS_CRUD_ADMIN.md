# Referências de Votação (CRUD no Gerencial)

Este recurso adiciona, na página `Gerencial` (`/gerencial/`), um botão "Referências" em cada linha da tabela de votações da proposição. Ao clicar, abre um subform para gerenciar registros na tabela `voting_referencias`, vinculados à `ProposicaoVotacao` da linha.

## Funcionalidades

- Listar referências existentes (URL e tipo).
- Adicionar nova referência (`url`, `kind`).
- Editar referência existente.
- Excluir referência.

Os tipos (`kind`) disponíveis:

- `web_page` – Página Web
- `sound` – Áudio
- `social_media` – Rede Social

## Endpoints (Admin AJAX)

- `GET /gerencial/ajax/referencias/list/?pv_id=<id>`
  - Retorna `{ ok, pv_id, dados: [{ id, url, kind, created_at }] }`.
- `POST /gerencial/ajax/referencias/create/`
  - Body: `pv_id`, `url`, `kind`.
- `POST /gerencial/ajax/referencias/update/`
  - Body: `ref_id`, `url?`, `kind?`.
- `POST /gerencial/ajax/referencias/delete/`
  - Body: `ref_id`.

Todos os endpoints requerem usuário com permissão de `staff` e incluem verificação CSRF.

## Uso

1. Acesse `/gerencial/?proposicao_id=<ID>`.
2. Na seção "Votações encontradas", clique em "Referências" na linha desejada.
3. Utilize o subform para adicionar, editar ou excluir.

## Observações

- Os registros são vinculados pelo `proposicao_votacao_id` da linha.
- A UI é não intrusiva (linha expansível) e mantém consistência visual com o restante do app.