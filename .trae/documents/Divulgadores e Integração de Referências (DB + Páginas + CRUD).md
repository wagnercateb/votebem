## Visão Geral
- Implementar suporte a “divulgadores” e vincular referências a votações, com exibição rica na página pública e CRUD simples para usuários divulgadores.
- Preservar compatibilidade com referências já existentes baseadas em ProposicaoVotacao.

## Mudanças de Banco de Dados
- Criar modelo Divulgador (tabela voting_divulgadores) no app voting:
  - email (EmailField, único), domain_parte (CharField), alias (CharField), tooltip (TextField opcional), icon_url (URLField opcional), user (ForeignKey auth_user opcional).
  - Índices: email e domain_parte.
- Alterar Referencia (tabela voting_referencias) em [models.py](file:///c:/Users/User/Dados/Tecnicos/HardESoftware/EmDesenvolvimento/VotoBomPython/django_votebem/voting/models.py#L305-L351):
  - Adicionar divulgador (ForeignKey para Divulgador, null=True, blank=True).
  - Adicionar title (CharField max_length=255, null=True, blank=True).
  - Adicionar votacao_votebem (ForeignKey para VotacaoVoteBem, null=True, blank=True) em [models.py](file:///c:/Users/User/Dados/Tecnicos/HardESoftware/EmDesenvolvimento/VotoBomPython/django_votebem/voting/models.py#L71-L90).
  - Constraint única: (divulgador, votacao_votebem) única quando ambos não nulos.
  - Índices em (divulgador) e (votacao_votebem) para performance.
- Migrações:
  - 000X_add_divulgadores_model
  - 000X_alter_referencias_add_divulgador_title_vv
  - Sem migração de dados automática para vincular referências antigas a VotacaoVoteBem; continuam funcionando via proposicao_votacao.

## Endpoints e Regras de Negócio
- Resolver “quem é divulgador?”: helper que retorna Divulgador pelo e-mail do request.user; se não existir, mostra mensagem de não autorizado ao “Opinar”.
- API pública de referências:
  - Estender /voting/referencias/list/ para aceitar vv_id (id de VotacaoVoteBem) além de pv_id (compatibilidade). Retornar alias, icon_url, title quando houver divulgador.
  - Ou criar /voting/votacao/<id>/referencias/ com JSON: [{url, kind, title, divulgador:{alias, icon_url}}].
- CRUD do divulgador:
  - Página /voting/opinar/ (login obrigatório) lista VotacaoVoteBem com badge Ativa/Inativa.
  - Em cada bloco, formular um único registro de Referencia por (divulgador, votacao_votebem): campos Title e URL; botões Salvar/Apagar.
  - Endpoints AJAX: POST /voting/opinar/referencias/save, POST /voting/opinar/referencias/delete (valida que ref.divulgador == divulgador atual).
- Middleware de bloqueio:
  - Em [middleware_site_lock.py](file:///c:/Users/User/Dados/Tecnicos/HardESoftware/EmDesenvolvimento/VotoBomPython/django_votebem/votebem/middleware_site_lock.py), manter whitelist de /voting/referencias/list/.
  - Adicionar whitelist para /voting/opinar (e assets necessários). Opcionalmente avaliar liberar páginas de votação públicas conforme a política.

## Páginas e Templates
- Página de votação individual (e.g. /voting/votacao/775/):
  - Adicionar seção “Entenda” renderizada a partir das referências ligadas ao VotacaoVoteBem atual.
  - Para cada referência:
    - Ícone: usar divulgador.icon_url se presente; caso contrário, ícone padrão por kind.
    - Rótulo abaixo do botão: alias do divulgador; se ausente, usar “Artigo” (web_page), “Vídeo” (social_media), “Áudio” (sound).
    - Hover com banner: se houver title, exibir overlay central na largura total com fonte grande verde escura e fundo amarelo claro 30% (visível enquanto o mouse estiver sobre o botão).
- Navbar:
  - Adicionar botão “Opinar” ao lado de “Ranking” para usuários autenticados que existem em Divulgador (por e-mail).
- Página “Opinar” (semelhante a [votacoes_management.html]):
  - Layout com cards para cada VotacaoVoteBem; após “Votada em:”, mostrar form simples de Referencia (Title + URL + Salvar/Apagar).
  - Não exibir controles administrativos fora do escopo.

## Frontend/JS
- Estender [referencias_manager.js](file:///c:/Users/User/Dados/Tecnicos/HardESoftware/EmDesenvolvimento/VotoBomPython/django_votebem/static/js/components/referencias_manager.js):
  - Suportar modo “buttons-grid” para público, além de tabela existente.
  - Carregar por vv_id quando disponível; fallback para pv_id.
  - Renderizar imagem do divulgador (icon_url) se houver, com fallback para ícone padrão por kind.
  - Implementar overlay de título (criar elemento fixo/absolute, mostrar em mouseenter, esconder em mouseleave).
- Manter componente read-only para público; CRUD apenas na página “Opinar”.

## Segurança e Acesso
- Acesso a “Opinar” exige login e presença em Divulgador (pelo e-mail).
- Endpoints de salvar/apagar verificam propriedade (ref.divulgador == divulgador atual).
- CSRF habilitado para POST.
- Site lock: whitelists necessárias atualizadas.

## Testes e Validação
- Testes de modelo: criação de Divulgador, constraints únicas, vínculos de Referencia.
- Testes de view: list por vv_id/pv_id; salvar/apagar respeitando regras.
- Testes manuais: página pública mostra “Entenda” com ícones/alias/banner; “Opinar” funciona fim-a-fim.

## Implantação e Migração
- Criar migrações, aplicar e validar integridade.
- Verificar desempenho (índices) em listagens de votações.
- Backups antes da migração; logs para monitorar erros de schema.

Conf