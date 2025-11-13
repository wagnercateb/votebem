# Separação de templates: Votos Oficiais (Admin vs Público)

Este documento registra a separação dos templates utilizados nas páginas:

- `http://localhost:8000/gerencial/?proposicao_id=...` (Admin)
- `http://localhost:8000/voting/votos/oficiais/?votacao_id=...` (Público)

Anteriormente, ambas renderizavam o mesmo include `voting/_votos_oficiais_content.html`,
o que misturava lógica/JS de gerenciamento (busca por proposição, importação de votos) com
o comportamento público (apenas filtros e estatísticas).

## O que mudou

- Criado include específico para Admin: `templates/admin/voting/_votos_oficiais_content_admin.html`
  - Mantém o formulário de busca por `proposicao_id` e o fluxo de importação via endpoints internos.
  - Mantém as tabelas e filtros.

- Criado include específico para Público: `templates/voting/_votos_oficiais_content_public.html`
  - Remove o formulário e o fluxo de importação (somente visualização/estatísticas).
  - Mantém as tabelas e filtros.

- Atualizados os templates que incluem o conteúdo:
  - Admin: `templates/admin/voting/votos_oficiais_app.html` agora inclui `admin/voting/_votos_oficiais_content_admin.html`.
  - Público: `templates/voting/votos_oficiais_app.html` agora inclui `voting/_votos_oficiais_content_public.html`.

## Motivações

- Evitar dependências cruzadas entre páginas de natureza diferente (admin x público).
- Tornar mais claro o que é responsabilidade de cada página e simplificar manutenção.

## Observações de manutenção

- Se houver evolução de estilos/JS comuns (filtros, ordenação, estatísticas), considere fatorar
  utilitários JS específicos e reutilizá-los em ambos sem reintroduzir compartilhamento de templates.
- O arquivo antigo `templates/voting/_votos_oficiais_content.html` permanece inalterado por compatibilidade,
  mas não é mais referenciado pelos templates atuais. Pode ser removido futuramente após revisão.