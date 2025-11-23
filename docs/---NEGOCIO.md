# Fontes de informação

## Prompts

### Referencias

- audio em https://notebooklm.google.com/:  create an audio of no more than 3 minutes. start with "Bem vindo ao debate, criado com a inteligência artificial do Google". Highlight the main aspects of the norm. emphasize ethical aspects. use easy language to teach the subject to people who know very little about it. Explain the acronyms you mention.

## API da Câmara

- swagger da API: https://dadosabertos.camara.leg.br/swagger/api.html?tab=api

- votações por período e por órgão:
https://dadosabertos.camara.leg.br/api/v2/votacoes?idOrgao=180&dataInicio=2025-01-01&ordem=DESC&ordenarPor=dataHoraRegistro

- TODAS as votações de uma proposicao:
https://dadosabertos.camara.leg.br/api/v2/votacoes?idProposicao=2270800&ordem=DESC&ordenarPor=dataHoraRegistro

- lista de votações por órgão e período. orgao=180=plenario 
(ver lista de orgaos em https://dadosabertos.camara.leg.br/api/v2/orgaos?itens=100&ordem=ASC&ordenarPor=id)

- se puser 01/01/ano, traz todas as votações do plenario no ano
https://dadosabertos.camara.leg.br/api/v2/votacoes?idOrgao=180&dataInicio=2023-01-01&ordem=DESC&ordenarPor=dataHoraRegistro

# Proposições aprovadas

## referencias

### backup
    INSERT INTO voting_referencias (url,kind,created_at,updated_at,proposicao_votacao_id) VALUES
        ('https://www.congressoemfoco.com.br/noticia/112740/programa-agora-tem-especialistas-e-oficialmente-sancionado-por-lula','web_page','2025-11-16 15:43:54.418250','2025-11-16 15:43:57.918923',32),
        ('/media/PEC_Blindagem_Impunidade_ou_Defesa_Parlamentar.m4a','sound','2025-11-16 16:22:11.357096','2025-11-16 16:22:11.357096',32),
        ('/media/Proposicao 2515300 - tarifa social da energia elétrica.pdf','web_page','2025-11-16 20:10:13.324587','2025-11-16 20:10:13.324587',30),
        ('/media/Nova_lei_de_tarifas_Justiça_ou_custo_social.m4a','sound','2025-11-17 14:57:19.409102','2025-11-17 14:57:19.409102',30);


### crime organizado
- https://www.camara.leg.br/noticias/1224884-camara-aprova-marco-legal-do-combate-ao-crime-organizado/
    - https://dadosabertos.camara.leg.br/api/v2/proposicoes/2579832
    - https://dadosabertos.camara.leg.br/api/v2/votacoes?idProposicao=2579832&ordem=DESC&ordenarPor=dataHoraRegistro

        {
            "dados": [
                {
                "id": "2579832-106",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-106",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T22:26:41",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Aprovada a Redação Final assinada pelo relator, Dep. Guilherme Derrite (PP/SP).",
                "aprovacao": 1
                },
                {
                "id": "2579832-105",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-105",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T22:26:21",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Aprovada a Emenda de Plenário nº 25. Sim: 349; Não: 40; Abstenção: 1; Total: 390.",
                "aprovacao": 1
                },
                {
                "id": "2579832-101",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-101",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T22:14:57",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Aprovada a Emenda de Plenário nº 1.",
                "aprovacao": 1
                },
                {
                "id": "2579832-99",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-99",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T22:11:52",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Rejeitada a preferência. Sim: 107; Não: 298; Abstenção: 2; Total: 407.",
                "aprovacao": 0
                },
                {
                "id": "2579832-96",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-96",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T22:01:24",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Mantido o texto. Sim: 298; Não: 109; Abstenção: 1; Total: 408.",
                "aprovacao": null
                },
                {
                "id": "2579832-95",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-95",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T21:48:46",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Rejeitada a Emenda de Plenário nº 33. Sim: 142; Não: 298; Abstenção: 1; Total: 441.",
                "aprovacao": 0
                },
                {
                "id": "2579832-72",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-72",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T21:32:49",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Rejeitadas as Emendas ao Substitutivo.",
                "aprovacao": 0
                },
                {
                "id": "2579832-67",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-67",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T21:31:18",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Mantido o texto.",
                "aprovacao": null
                },
                {
                "id": "2579832-62",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-62",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T21:24:57",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Aprovado o Substitutivo ao Projeto de Lei nº 5.582, de 2025, adotado pelo relator da Comissão de Segurança Pública e Combate ao Crime Organizado, ressalvados os destaques. Sim: 370; Não: 110; Abstenção: 3; Total: 483.",
                "aprovacao": 1
                },
                {
                "id": "2579832-61",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-61",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T20:35:55",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Rejeitada a Preferência. Sim: 156; Não: 306; Total: 462.",
                "aprovacao": 0
                },
                {
                "id": "2579832-54",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-54",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T19:51:52",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Aprovado o Requerimento. Sim: 335; Não: 111; Total: 446.",
                "aprovacao": 1
                },
                {
                "id": "2579832-49",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-49",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T18:58:32",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Rejeitado o Requerimento. Sim: 114; Não: 335; Total: 449.",
                "aprovacao": 0
                },
                {
                "id": "2579832-41",
                "uri": "https://dadosabertos.camara.leg.br/api/v2/votacoes/2579832-41",
                "data": "2025-11-18",
                "dataHoraRegistro": "2025-11-18T18:11:45",
                "siglaOrgao": "PLEN",
                "uriOrgao": "https://dadosabertos.camara.leg.br/api/v2/orgaos/180",
                "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/80366",
                "proposicaoObjeto": null,
                "uriProposicaoObjeto": null,
                "descricao": "Rejeitado o Requerimento. Sim: 110; Não: 316; Total: 426.",
                "aprovacao": 0
                }
            ],
            "links": [
                {
                "rel": "self",
                "href": "https://dadosabertos.camara.leg.br/api/v2/votacoes?idProposicao=2579832&ordem=DESC&ordenarPor=dataHoraRegistro"
                },
                {
                "rel": "first",
                "href": "https://dadosabertos.camara.leg.br/api/v2/votacoes?idProposicao=2579832&ordem=DESC&ordenarPor=dataHoraRegistro&pagina=1&itens=100"
                },
                {
                "rel": "last",
                "href": "https://dadosabertos.camara.leg.br/api/v2/votacoes?idProposicao=2579832&ordem=DESC&ordenarPor=dataHoraRegistro&pagina=1&itens=100"
                }
            ]
            }
