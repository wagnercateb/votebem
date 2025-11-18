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