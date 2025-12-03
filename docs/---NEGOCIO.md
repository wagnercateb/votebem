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

# Imprensa e favoritos do navegador

                <DT><H3 ADD_DATE="1760283851" LAST_MODIFIED="1764589927">VoteBem</H3>
                <DL><p>
                    <DT><H3 ADD_DATE="1760283851" LAST_MODIFIED="1760283873">semelhantes</H3>
                    <DL><p>
                        <DT><A HREF="https://quemfoiquem.org.br/" ADD_DATE="1760283820">quemfoiquem.org.br</A>
                        <DT><A HREF="https://placarcongresso.com/pages/s-ranking.html" ADD_DATE="1760283873" 
                        ... (icone)
                    ">Placar Congresso - Ranking Senado Federal</A>
                    </DL><p>
                    <DT><A HREF="https://dadosabertos.camara.leg.br/#" ADD_DATE="1760229584" 
                        ... (icone)
                     - index indice assuntos principais</A>
                    <DT><A HREF="https://www2.camara.leg.br/transparencia/servicos-ao-cidadao/relacionamento-e-participacao" ADD_DATE="1763903611" 
                        ... (icone)
                    ">Relacionamento e participação — Portal da Câmara dos Deputados</A>
                    <DT><A HREF="https://evc.camara.leg.br/programas/oficina-de-atuacao-no-parlamento/" ADD_DATE="1763903645" 
                        ... (icone)
                    ">Oficina de Atuação no Parlamento - EVC</A>
                    <DT><A HREF="https://dadosabertos.camara.leg.br/community/blogger.html" ADD_DATE="1763903661" 
                    ... (icone)
                    ==">Blogger da Câmara - cita votobom</A>
                    <DT><A HREF="https://www.camara.leg.br/agenda?categorias=Plen%C3%A1rio,Congresso" ADD_DATE="1763903716" 
                        ... (icone)
                    ">A Agenda da Câmara dos Deputados - Portal da Câmara dos Deputados</A>
                    <DT><A HREF="https://www1.folha.uol.com.br/fsp/fac-simile/2025/12/01/" ADD_DATE="1764588166" 
                        ... (icone)
                    ">FSP | Folha edicao impressa - por data</A>
                    <DT><A HREF="https://acervo.folha.uol.com.br/digital/leitor.do?numero=51212&anchor=6531219&maxTouch=0&pd=db41acf838b17513aabf8fabb9a37531" ADD_DATE="1764588209" 
                        ... (icone)
                    ">Folha de S.Paulo - por data - ed impressa</A>
                    <DT><A HREF="https://acervo.folha.uol.com.br/digital/edicoes-recentes.do" ADD_DATE="1764588270" 
                        ... (icone)
                    ">Folha de S.Paulo - edicoes por assunto e data periodo</A>
                    <DT><A HREF="https://digital.estadao.com.br/o-estado-de-s-paulo/20241221" ADD_DATE="1764589306" 
                        ... (icone)
                    ">Estadao por data - so tem um ano</A>
                    <DT><A HREF="https://acervo.estadao.com.br/linha-do-tempo/" ADD_DATE="1764589342">Estadao - acervo por data periodo completo</A>
                    <DT><A HREF="https://acervo.estadao.com.br/procura/#!/c%C3%A2mara%20aprova%20votos/Acervo/capa//1/2020/" ADD_DATE="1764589927">Estadao acervo pesquisa total completa por votos</A>
                </DL><p>
                <DT><A HREF="https://app.improvmx.com/" ADD_DATE="1762802507" 
                    ... (icone)
                ">ImprovMX — Free email forwarding</A>
                <DT><A HREF="http://investir.website:8081/#/garimpe" ADD_DATE="1762813239" 
                    ... (icone)
                ">investir.website</A>
            </DL><p>
