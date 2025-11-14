# Prioridade em ProposicaoVotacao (Admin)

Este documento descreve a adição do campo `prioridade` (inteiro, opcional) ao modelo `ProposicaoVotacao` e sua edição na tela administrativa de votos oficiais.

## O que mudou

- Modelo `voting.models.ProposicaoVotacao` ganhou o campo `prioridade: IntegerField(null=True, blank=True)`.
- Endpoint AJAX novo em `gerencial/ajax/proposicao-votacao/update-prioridade/` para atualizar a prioridade por registro.
- Endpoint `gerencial/ajax/proposicao-votacoes/` passou a incluir `pv_id` e `prioridade` no JSON quando os dados vêm do banco (`source: 'db'`).
- Template `templates/admin/voting/_votos_oficiais_content_admin.html` agora exibe uma coluna "Prioridade" com um textbox por linha (quando houver `pv_id`). A atualização é enviada via AJAX ao alterar, sair do campo ou pressionar Enter.

## Como usar

1. Acesse `http://localhost:8000/gerencial/?proposicao_id=<ID>`.
2. Carregue as votações da proposição pelo formulário.
3. Quando houver registros no banco, a tabela exibirá a coluna "Prioridade" editável.
4. Edite o valor (vazio para remover prioridade) e confirme com Enter ou saindo do campo. O feedback visual indica sucesso/erro.

## Observações técnicas

- O endpoint exige autenticação (staff) e CSRF token; o template busca `csrftoken` nos cookies.
- Para itens oriundos da API (ainda não persistidos), a coluna mostra "—" pois não há `pv_id`.
- Migrações: `makemigrations voting` e `migrate` atualizam o schema.

## Manutenção

- Se necessário, inclua `prioridade` em `admin.py` (`ProposicaoVotacaoAdmin`) para listagens no Django Admin.
- A ordenação da exibição (frontend) pode futuramente utilizar `prioridade` para definir a ordem preferencial.