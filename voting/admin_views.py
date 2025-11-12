from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
import time
import json
import logging
import re
import requests
from .models import Proposicao, ProposicaoVotacao, VotacaoDisponivel, Voto, Congressman, CongressmanVote
from django.contrib.auth.models import User
from .services.camara_api import camara_api, CamaraAPIService
from votebem.utils.devlog import dev_log  # Dev logger for console + file output
from django.db import transaction

@staff_member_required
def admin_dashboard(request):
    """
    Custom admin dashboard with statistics and management tools
    Similar to the PHP admin interface functionality
    """
    context = {
        'total_proposicoes': Proposicao.objects.count(),
        'total_votacoes_disponiveis': VotacaoDisponivel.objects.count(),
        'votacoes_ativas': VotacaoDisponivel.objects.filter(ativo=True).count(),
        'total_votos_populares': Voto.objects.count(),
        'total_congressistas': Congressman.objects.count(),
        'total_votos_congressistas': CongressmanVote.objects.count(),
        'total_usuarios': User.objects.count(),
        'ultima_proposicao': Proposicao.objects.first(),
        'votacoes_recentes': VotacaoDisponivel.objects.filter(ativo=True)[:5],
    }
    
    return render(request, 'admin/voting/admin_dashboard.html', context)


@staff_member_required
def votos_oficiais_app(request):
    """Subpágina embutível de Votação oficial com filtros e estatísticas client-side.
    Aceita query param `votacao_id` para carregar votos de uma votação específica.
    """
    votacao_id = request.GET.get('votacao_id')
    votacao = None
    votos_data = []
    if votacao_id:
        try:
            votacao = VotacaoDisponivel.objects.select_related('proposicao').get(pk=int(votacao_id))
            # Votação oficial: por proposição
            registros = (
                CongressmanVote.objects
                .select_related('congressman')
                .filter(proposicao=votacao.proposicao)
            )
            for r in registros:
                votos_data.append({
                    'nome': r.congressman.nome,
                    'id_cadastro': r.congressman.id_cadastro,
                    'partido': r.congressman.partido or '',
                    'uf': r.congressman.uf or '',
                    'voto': r.get_voto_display_text(),
                })
        except Exception:
            votacao = None

    context = {
        'votacao': votacao,
        'votos_json': json.dumps(votos_data, ensure_ascii=False),
        'prefill_proposicao_id': request.GET.get('proposicao_id') or '',
    }
    return render(request, 'admin/voting/votos_oficiais_app.html', context)


@staff_member_required
def ajax_import_congress_votes(request):
    """
    Importa votos oficiais de uma votação específica (proposicao_id + sufixo/consulta_id)
    e salva em CongressmanVote. Retorna resumo e lista de votos para atualizar UI.
    """
    try:
        proposicao_id = request.GET.get('proposicao_id')
        consulta_id = request.GET.get('consulta_id') or request.GET.get('votacao_sufixo') or request.GET.get('votacao_id')
        if not proposicao_id:
            return JsonResponse({'ok': False, 'error': 'proposicao_id é obrigatório'}, status=400)
        if not consulta_id:
            return JsonResponse({'ok': False, 'error': 'consulta_id (sufixo da votação) é obrigatório'}, status=400)

        # Normalizar/validar números
        try:
            prop_id_int = int(str(proposicao_id).strip())
            sufixo_int = int(str(consulta_id).strip()) if '-' not in str(consulta_id) else int(str(consulta_id).strip().split('-')[-1])
        except Exception:
            return JsonResponse({'ok': False, 'error': 'IDs inválidos fornecidos'}, status=400)

        # Construir ID de votação no formato esperado pela API: "<proposicao_id>-<sufixo>"
        votacao_composta_id = f"{prop_id_int}-{sufixo_int}"
        api_url_votes = f"{CamaraAPIService.BASE_URL}/votacoes/{votacao_composta_id}/votos"

        # Garantir que a Proposição exista
        proposicao, _ = Proposicao.objects.get_or_create(
            id_proposicao=prop_id_int,
            defaults={
                'titulo': '', 'ementa': '', 'tipo': '', 'numero': 0, 'ano': 0,
            }
        )

        # Buscar detalhes e votos individuais na API
        detalhes_votacao = camara_api.get_votacao_details(votacao_composta_id) or {}
        dados_det = detalhes_votacao.get('dados') or {}
        votos_individuais = camara_api.get_votacao_votos(votacao_composta_id)

        # Converter placar oficial
        try:
            sim_count = int(dados_det.get('placarSim') or 0)
            nao_count = int(dados_det.get('placarNao') or 0)
        except Exception:
            sim_count = 0
            nao_count = 0
        if (sim_count == 0 and nao_count == 0) and isinstance(votos_individuais, list):
            for v in votos_individuais:
                tipo = (v.get('tipoVoto') or '').strip().lower()
                if tipo == 'sim':
                    sim_count += 1
                elif tipo in ('não', 'nao'):
                    nao_count += 1

        # Mapear e inserir/atualizar votes em CongressmanVote
        from unicodedata import normalize
        def norm(s: str) -> str:
            s = (s or '').strip().lower()
            try:
                return ''.join(c for c in normalize('NFKD', s) if not ord(c) > 127)
            except Exception:
                return s

        congressmen = list(Congressman.objects.only('id', 'id_cadastro', 'nome', 'partido', 'uf'))
        by_id = {cm.id_cadastro: cm for cm in congressmen if cm.id_cadastro}
        by_name = {norm(cm.nome): cm for cm in congressmen if cm.nome}

        def map_voto(tipo: str):
            t = (tipo or '').strip().lower()
            if t == 'sim':
                return 1
            if t == 'não' or t == 'nao':
                return -1
            if t == 'abstenção' or t == 'abstencao':
                return 0
            return None

        created = 0
        updated = 0
        skipped = 0
        votos_out = []

        for voto in votos_individuais or []:
            dep = voto.get('deputado') or {}
            dep_id = (
                dep.get('id')
                or voto.get('idDeputado')
                or voto.get('deputadoId')
                or voto.get('id_deputado')
            )
            # fallback: procurar qualquer chave que pareça id de deputado
            if dep_id is None and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'id' in kl and 'deput' in kl and v is not None:
                            dep_id = v
                            break
                except Exception:
                    pass
            try:
                dep_id = int(dep_id) if dep_id is not None else None
            except Exception:
                dep_id = None

            nome_dep = (
                dep.get('nome')
                or voto.get('nome')
                or voto.get('deputadoNome')
                or voto.get('nome_deputado')
            )
            # fallback: procurar nome em qualquer chave
            if not nome_dep and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'nome' in kl and 'deput' in kl and v:
                            nome_dep = v
                            break
                except Exception:
                    pass

            voto_tipo = voto.get('tipoVoto') or voto.get('tipo_voto')
            voto_val = map_voto(voto_tipo)

            cm = None
            if dep_id and dep_id in by_id:
                cm = by_id.get(dep_id)
            elif nome_dep:
                cm = by_name.get(norm(nome_dep))
            if not cm and dep_id:
                try:
                    cm = Congressman.objects.create(
                        id_cadastro=dep_id,
                        nome=nome_dep or f"Deputado {dep_id}",
                        partido=(dep.get('siglaPartido') or ''),
                        uf=(dep.get('siglaUf') or ''),
                        ativo=True,
                    )
                    by_id[dep_id] = cm
                    by_name[norm(cm.nome)] = cm
                    created += 0  # only count votes below
                except Exception:
                    cm = None

            if not cm:
                skipped += 1
                continue

            obj, was_created = CongressmanVote.objects.update_or_create(
                congressman=cm,
                proposicao=proposicao,
                defaults={'voto': voto_val, 'congress_vote_id': sufixo_int}
            )
            if was_created:
                created += 1
            else:
                updated += 1

            votos_out.append({
                'nome': cm.nome,
                'id_cadastro': cm.id_cadastro,
                'partido': cm.partido or '',
                'uf': cm.uf or '',
                'voto': obj.get_voto_display_text(),
            })

        return JsonResponse({
            'ok': True,
            'proposicao_id': prop_id_int,
            'consulta_id': sufixo_int,
            'votacao_id': votacao_composta_id,
            'sim': sim_count,
            'nao': nao_count,
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'votos': votos_out,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Erro ao importar: {e}', 'api_url': api_url_votes}, status=502)


@staff_member_required
def congressistas_update(request):
    """Update Congressman table from Câmara API with optional idLegislatura param (default 57).
    Fetches all pages, deduplicates by id (keep last), aggregates party siglas history.
    """
    id_legislatura = request.GET.get('idLegislatura')
    if not id_legislatura:
        id_legislatura = '57'

    created = 0
    updated = 0
    errors = 0
    api_url = (
        f"https://dadosabertos.camara.leg.br/api/v2/deputados"
    )
    params = {
        'idLegislatura': id_legislatura,
        'ordem': 'ASC',
        'ordenarPor': 'nome',
        'itens': 100
    }

    result_summary = None
    if request.GET.get('run') == '1':
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            # Fetch all pages
            page = 1
            itens = 100
            deputados_all = []
            while True:
                params_page = {
                    'idLegislatura': id_legislatura,
                    'ordem': 'ASC',
                    'ordenarPor': 'nome',
                    'itens': itens,
                    'pagina': page,
                }
                resp = requests.get("https://dadosabertos.camara.leg.br/api/v2/deputados", params=params_page, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                dados = data.get('dados', [])
                if not dados:
                    break
                deputados_all.extend(dados)
                links = data.get('links', [])
                has_next = any(l.get('rel') == 'next' for l in links)
                if not has_next:
                    break
                page += 1
                if page > 1000:
                    break

            # Aggregate by id (keep last) and collect party siglas
            agg = {}
            order_counter = 0
            for dep in deputados_all:
                dep_id = dep.get('id')
                nome = dep.get('nome')
                partido = dep.get('siglaPartido') or ''
                uf = dep.get('siglaUf') or ''
                foto_url = dep.get('urlFoto') or ''
                if dep_id is None or not nome:
                    continue
                order_counter += 1
                entry = agg.get(dep_id, {'nome': nome, 'uf': uf, 'foto_url': foto_url, 'partido': partido, 'siglas': [], 'order': order_counter})
                if partido and partido not in entry['siglas']:
                    entry['siglas'].append(partido)
                entry['nome'] = nome
                entry['uf'] = uf
                entry['foto_url'] = foto_url or entry['foto_url']
                entry['partido'] = partido or entry['partido']
                entry['order'] = order_counter
                agg[dep_id] = entry

            # Persist aggregated deputies
            for dep_id, entry in agg.items():
                try:
                    nome = entry['nome']
                    partido = entry['partido']
                    uf = entry['uf']
                    foto_url = entry['foto_url']
                    partidos_hist = ", ".join(entry['siglas']) if entry['siglas'] else None
                    try:
                        cm = Congressman.objects.get(id_cadastro=dep_id)
                        cm.nome = nome
                        cm.partido = partido
                        cm.uf = uf
                        cm.foto_url = foto_url or cm.foto_url
                        cm.partidos_historico = partidos_hist
                        cm.ativo = True
                        cm.save()
                        updated += 1
                    except Congressman.DoesNotExist:
                        cm = Congressman.objects.filter(nome__iexact=nome).first()
                        if cm:
                            cm.id_cadastro = dep_id
                            cm.partido = partido
                            cm.uf = uf
                            cm.foto_url = foto_url or cm.foto_url
                            cm.partidos_historico = partidos_hist
                            cm.ativo = True
                            cm.save()
                            updated += 1
                        else:
                            Congressman.objects.create(
                                id_cadastro=dep_id,
                                nome=nome,
                                partido=partido,
                                uf=uf,
                                foto_url=foto_url or None,
                                partidos_historico=partidos_hist,
                                ativo=True,
                            )
                            created += 1
                except Exception:
                    errors += 1

            result_summary = {
                'total_api': len(deputados_all),
                'created': created,
                'updated': updated,
                'errors': errors,
                'id_legislatura': id_legislatura,
            }
            messages.success(request, f"Deputados atualizados (idLegislatura {id_legislatura}): total {len(deputados_all)}, criados {created}, atualizados {updated}, erros {errors}.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar deputados: {e}")

    context = {
        'id_legislatura': id_legislatura,
        'result_summary': result_summary,
    }
    return render(request, 'admin/voting/congressistas_update.html', context)


@staff_member_required
def votacao_obter_votacao(request, pk):
    """Fetch official voting for the proposition linked to a VotacaoDisponivel and store individual votes."""
    votacao = get_object_or_404(VotacaoDisponivel, pk=pk)
    proposicao = votacao.proposicao
    if not proposicao or not proposicao.id_proposicao:
        messages.error(request, 'Proposição sem id_proposicao; não é possível consultar votação oficial.')
        return redirect('gerencial:votacao_edit', pk=pk)

    try:
        logger = logging.getLogger(__name__)
        def log_step(message, data=None):
            prefix = f"[VotacaoImport id={votacao.id}] "
            if data is not None:
                try:
                    line = prefix + message + " | " + json.dumps(data, ensure_ascii=False)
                except Exception:
                    line = prefix + message + f" | {data}"
            else:
                line = prefix + message
            dev_log(line)
            try:
                logger.info(line)
            except Exception:
                pass
        log_step("Starting import flow", {"proposicao_id_proposicao": proposicao.id_proposicao})
        # Step 1: get all votações of the proposição
        votos_list = camara_api.get_proposicao_votacoes(proposicao.id_proposicao)
        log_step("Fetched votações list for proposição", {"count": len(votos_list) if isinstance(votos_list, list) else None})

        if not votos_list:
            messages.error(request, 'Nenhuma votação oficial encontrada para esta proposição.')
            return redirect('gerencial:votacao_edit', pk=pk)

        # Step 2: find main votação by descricao contains aprov/rejeit + proposta
        main_votacao_id = None
        for v in votos_list:
            desc = (v.get('descricao') or '').lower()
            if (('aprovad' in desc or 'rejeitad' in desc) and 'proposta' in desc):
                main_votacao_id = v.get('id')
                break
        # Fallback: first item
        if not main_votacao_id:
            main_votacao_id = votos_list[0].get('id')

        if not main_votacao_id:
            messages.error(request, 'Não foi possível determinar a votação principal.')
            return redirect('gerencial:votacao_edit', pk=pk)
        log_step("Selected main votação", {"main_votacao_id": main_votacao_id})

        # Step 3: get voting details (for official counts) and individual votes
        detalhes_votacao = camara_api.get_votacao_details(main_votacao_id) or {}
        dados_det = detalhes_votacao.get('dados') or {}
        votos_individuais = camara_api.get_votacao_votos(main_votacao_id)
        log_step("Fetched votação details and individual votes", {
            "details_keys": list(detalhes_votacao.keys()) if isinstance(detalhes_votacao, dict) else None,
            "dados_det_keys": list(dados_det.keys()) if isinstance(dados_det, dict) else None,
            "individual_votes_count": len(votos_individuais) if isinstance(votos_individuais, list) else None,
        })
        try:
            sample = []
            for i in range(min(3, len(votos_individuais) if isinstance(votos_individuais, list) else 0)):
                v = votos_individuais[i]
                dep_sample = v.get('deputado') if isinstance(v, dict) else None
                sample.append({
                    'keys': list(v.keys()) if isinstance(v, dict) else None,
                    'deputado_keys': list(dep_sample.keys()) if isinstance(dep_sample, dict) else None,
                    'tipoVoto': v.get('tipoVoto') if isinstance(v, dict) else None,
                })
            if sample:
                log_step("Vote payload sample", {"items": sample})
        except Exception:
            pass

        # Extract numeric congress vote id (e.g., from '2270800-160' -> 160)
        congress_vote_numeric_id = None
        try:
            if isinstance(main_votacao_id, str) and '-' in main_votacao_id:
                congress_vote_numeric_id = int(main_votacao_id.split('-')[-1])
            elif isinstance(main_votacao_id, (int, float)):
                congress_vote_numeric_id = int(main_votacao_id)
        except Exception:
            congress_vote_numeric_id = None

        # Map vote string to integers
        def map_voto(tipo: str):
            t = (tipo or '').strip().lower()
            if t == 'sim':
                return 1
            if t == 'não' or t == 'nao':
                return -1
            if t == 'abstenção' or t == 'abstencao':
                return 0
            return None
        # Count SIM/NÃO independently of DB matches; prefer official counts from details
        # Fallback to computing from individual votes when details are missing
        sim_count = int(dados_det.get('placarSim') or 0)
        nao_count = int(dados_det.get('placarNao') or 0)
        if (sim_count == 0 and nao_count == 0) and votos_individuais:
            sim_count = 0
            nao_count = 0
            for v in votos_individuais:
                tipo = (v.get('tipoVoto') or '').strip().lower()
                if tipo == 'sim':
                    sim_count += 1
                elif tipo in ('não', 'nao'):
                    nao_count += 1
        log_step("Computed official counts", {"placarSim": sim_count, "placarNao": nao_count})

        # Prepare congressman lookup maps to reduce skipping
        from unicodedata import normalize
        def norm(s: str) -> str:
            s = (s or '').strip().lower()
            try:
                return ''.join(c for c in normalize('NFKD', s) if not ord(c) > 127)
            except Exception:
                return s

        congressmen = list(Congressman.objects.only('id', 'id_cadastro', 'nome'))
        by_id = {cm.id_cadastro: cm for cm in congressmen if cm.id_cadastro}
        by_name = {norm(cm.nome): cm for cm in congressmen if cm.nome}

        created = 0
        updated = 0
        skipped = 0
        auto_created_cm = 0

        for voto in votos_individuais:
            dep = voto.get('deputado') or {}
            # Heuristic: if 'deputado' key missing, look for any key containing 'deput'
            if not dep and isinstance(voto, dict):
                try:
                    cand_keys = [k for k in voto.keys() if isinstance(k, str) and 'deput' in k.lower()]
                    for ck in cand_keys:
                        if isinstance(voto.get(ck), dict):
                            dep = voto.get(ck) or {}
                            log_step("Detected alternative deputy container", {"key": ck})
                            break
                except Exception:
                    pass
            # Robust deputy id/name extraction across possible API variations
            dep_id = (
                dep.get('id')
                or voto.get('idDeputado')
                or voto.get('deputadoId')
                or voto.get('id_deputado')
            )
            # Generic scan for any key that looks like deputy id
            if dep_id is None and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'id' in kl and 'deput' in kl and v is not None:
                            dep_id = v
                            log_step("Detected deputy id from generic key", {"key": k, "value": v})
                            break
                except Exception:
                    pass
            try:
                if dep_id is not None:
                    dep_id = int(dep_id)
            except Exception:
                pass
            nome_dep = (
                dep.get('nome')
                or voto.get('nome')
                or voto.get('deputadoNome')
                or voto.get('nome_deputado')
            )
            if not nome_dep and isinstance(voto, dict):
                try:
                    for k, v in voto.items():
                        kl = k.lower() if isinstance(k, str) else ''
                        if 'nome' in kl and 'deput' in kl and v:
                            nome_dep = v
                            log_step("Detected deputy name from generic key", {"key": k, "value": v})
                            break
                except Exception:
                    pass
            voto_tipo = voto.get('tipoVoto') or voto.get('tipo_voto')
            voto_val = map_voto(voto_tipo)

            cm = None
            if dep_id and dep_id in by_id:
                cm = by_id.get(dep_id)
            elif nome_dep:
                cm = by_name.get(norm(nome_dep))
            if not cm:
                # As a robustness fallback, auto-create congressman from vote data when ID is present
                if dep_id:
                    try:
                        cm = Congressman.objects.create(
                            id_cadastro=dep_id,
                            nome=nome_dep or f"Deputado {dep_id}",
                            partido=(dep.get('siglaPartido') or ''),
                            uf=(dep.get('siglaUf') or ''),
                            ativo=True,
                        )
                        by_id[dep_id] = cm
                        by_name[norm(cm.nome)] = cm
                        auto_created_cm += 1
                        log_step("Auto-created missing congressman", {"id_cadastro": dep_id, "nome": cm.nome, "partido": cm.partido, "uf": cm.uf})
                    except Exception:
                        cm = None
                        log_step("Failed to auto-create congressman", {"id_cadastro": dep_id, "nome": nome_dep})
                if not cm:
                    skipped += 1
                    log_step("Skipped vote: no congressman match", {"dep_id": dep_id, "nome_dep": nome_dep, "tipoVoto": voto_tipo, "raw_vote": voto})
                    continue

            obj, was_created = CongressmanVote.objects.update_or_create(
                congressman=cm,
                proposicao=proposicao,
                defaults={'voto': voto_val, 'congress_vote_id': congress_vote_numeric_id}
            )
            if congress_vote_numeric_id is not None:
                try:
                    if getattr(obj, 'congress_vote_id', None) != congress_vote_numeric_id:
                        obj.congress_vote_id = congress_vote_numeric_id
                        obj.save(update_fields=['congress_vote_id'])
                except Exception:
                    pass
            if was_created:
                created += 1
                log_step("Inserted CongressmanVote", {"congressman_id": cm.id, "id_cadastro": cm.id_cadastro, "voto": voto_val})
            else:
                updated += 1
                log_step("Updated CongressmanVote", {"congressman_id": cm.id, "id_cadastro": cm.id_cadastro, "voto": voto_val})

        # Update official counts on votacao
        try:
            votacao.sim_oficial = sim_count
            votacao.nao_oficial = nao_count
            votacao.save(update_fields=['sim_oficial', 'nao_oficial'])
            log_step("Saved official counts on VotacaoDisponivel", {"sim_oficial": sim_count, "nao_oficial": nao_count})
        except Exception:
            pass

        log_step("Import summary", {"novos": created, "atualizados": updated, "ignorados": skipped, "deputados_criados": auto_created_cm})
        messages.success(
            request,
            f"Votação oficial importada (id {main_votacao_id}). SIM: {sim_count}, NÃO: {nao_count}, "
            f"novos: {created}, atualizados: {updated}, ignorados: {skipped}, deputados criados: {auto_created_cm}."
        )
    except Exception as e:
        messages.error(request, f"Erro ao obter votação oficial: {e}")

    return redirect('gerencial:votacao_edit', pk=pk)

@staff_member_required
def proposicoes_statistics(request):
    """
    Display statistics about propositions similar to PHP admin
    """
    stats = {
        'por_tipo': Proposicao.objects.values('tipo').annotate(count=Count('id')).order_by('-count'),
        'por_ano': Proposicao.objects.values('ano').annotate(count=Count('id')).order_by('-ano'),
        'por_estado': Proposicao.objects.values('estado').annotate(count=Count('id')).order_by('-count'),
        'com_votacao': Proposicao.objects.filter(votacaodisponivel__isnull=False).distinct().count(),
        'sem_votacao': Proposicao.objects.filter(votacaodisponivel__isnull=True).count(),
    }
    
    return render(request, 'admin/voting/proposicoes_statistics.html', {'stats': stats})


@staff_member_required
def proposicoes_list(request):
    """
    List and manage propositions
    """
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Get search parameters
    search = request.GET.get('search', '')
    tipo_filter = request.GET.get('tipo', '')
    ano_filter = request.GET.get('ano', '')
    estado_filter = request.GET.get('estado', '')
    
    # Base queryset
    proposicoes = Proposicao.objects.all().order_by('-ano', '-numero')
    
    # Apply filters
    if search:
        proposicoes = proposicoes.filter(
            Q(titulo__icontains=search) |
            Q(ementa__icontains=search) |
            Q(id_proposicao__icontains=search)
        )
    
    if tipo_filter:
        proposicoes = proposicoes.filter(tipo=tipo_filter)
    
    if ano_filter:
        proposicoes = proposicoes.filter(ano=ano_filter)
    
    if estado_filter:
        proposicoes = proposicoes.filter(estado=estado_filter)
    
    # Pagination
    paginator = Paginator(proposicoes, 25)  # Show 25 propositions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Annotate preferred votação id for each proposição on the current page
    # Choose an active votação if present; otherwise use the first available
    try:
        for p in page_obj:
            qs = VotacaoDisponivel.objects.filter(proposicao_id=p.id)
            preferred = qs.filter(ativo=True).order_by('id').first() or qs.order_by('id').first()
            p.preferred_votacao_id = preferred.id if preferred else None
            p.has_votacao = qs.exists()
    except Exception:
        # In case of any unexpected error, ensure attributes exist to avoid template errors
        for p in page_obj:
            p.preferred_votacao_id = None
            p.has_votacao = False
    
    # Get filter options
    tipos_disponiveis = Proposicao.objects.values_list('tipo', flat=True).distinct().order_by('tipo')
    anos_disponiveis = Proposicao.objects.values_list('ano', flat=True).distinct().order_by('-ano')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_filter': tipo_filter,
        'ano_filter': ano_filter,
        'estado_filter': estado_filter,
        'tipos_disponiveis': tipos_disponiveis,
        'anos_disponiveis': anos_disponiveis,
        'total_proposicoes': proposicoes.count(),
    }
    
    return render(request, 'admin/voting/proposicoes_list.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def proposicao_edit(request, pk):
    """
    View para editar uma proposição específica
    """
    try:
        proposicao = get_object_or_404(Proposicao, pk=pk)
    except:
        messages.error(request, 'Proposição não encontrada.')
        return redirect('gerencial:proposicoes_list')
    
    if request.method == 'POST':
        # Processar formulário de edição
        titulo = request.POST.get('titulo', '').strip()
        ementa = request.POST.get('ementa', '').strip()
        tipo = request.POST.get('tipo', '').strip()
        numero = request.POST.get('numero', '').strip()
        ano = request.POST.get('ano', '').strip()
        estado = request.POST.get('estado', '').strip()
        
        # Validações básicas
        if not titulo:
            messages.error(request, 'Título é obrigatório.')
        elif not tipo:
            messages.error(request, 'Tipo é obrigatório.')
        elif not numero:
            messages.error(request, 'Número é obrigatório.')
        elif not ano:
            messages.error(request, 'Ano é obrigatório.')
        else:
            try:
                # Atualizar proposição
                proposicao.titulo = titulo
                proposicao.ementa = ementa
                proposicao.tipo = tipo
                proposicao.numero = int(numero)
                proposicao.ano = int(ano)
                proposicao.estado = estado
                proposicao.save()
                
                messages.success(request, f'Proposição "{proposicao.titulo}" atualizada com sucesso!')
                return redirect('gerencial:proposicoes_list')
                
            except ValueError:
                messages.error(request, 'Número e ano devem ser valores numéricos.')
            except Exception as e:
                messages.error(request, f'Erro ao salvar proposição: {str(e)}')
    
    # Buscar votações relacionadas
    votacoes = proposicao.votacaodisponivel_set.all()
    
    context = {
        'proposicao': proposicao,
        'votacoes': votacoes,
        'title': f'Editar Proposição - {proposicao.tipo} {proposicao.numero}/{proposicao.ano}',
    }
    
    return render(request, 'admin/voting/proposicao_edit.html', context)

@staff_member_required
def votacao_edit(request, pk):
    """Edit a votacao disponivel"""
    votacao = get_object_or_404(VotacaoDisponivel, pk=pk)
    
    if request.method == 'POST':
        # Handle form submission
        votacao.titulo = request.POST.get('titulo', votacao.titulo)
        votacao.resumo = request.POST.get('resumo', votacao.resumo)
        
        # Handle datetime fields
        data_hora_votacao = request.POST.get('data_hora_votacao')
        if data_hora_votacao:
            try:
                votacao.data_hora_votacao = timezone.datetime.fromisoformat(data_hora_votacao.replace('T', ' '))
            except ValueError:
                pass
        
        no_ar_desde = request.POST.get('no_ar_desde')
        if no_ar_desde:
            try:
                votacao.no_ar_desde = timezone.datetime.fromisoformat(no_ar_desde.replace('T', ' '))
            except ValueError:
                pass
        
        no_ar_ate = request.POST.get('no_ar_ate')
        if no_ar_ate:
            try:
                votacao.no_ar_ate = timezone.datetime.fromisoformat(no_ar_ate.replace('T', ' '))
            except ValueError:
                pass
        else:
            votacao.no_ar_ate = None
        
        # Handle integer fields
        try:
            votacao.sim_oficial = int(request.POST.get('sim_oficial', 0))
            votacao.nao_oficial = int(request.POST.get('nao_oficial', 0))
        except ValueError:
            pass
        
        # Handle boolean field
        votacao.ativo = request.POST.get('ativo') == 'on'
        
        try:
            votacao.save()
            messages.success(request, 'Votação atualizada com sucesso!')
            return redirect('gerencial:votacao_edit', pk=pk)
        except Exception as e:
            messages.error(request, f'Erro ao salvar votação: {str(e)}')
    
    # Get related votes count
    total_votos = votacao.get_total_votos_populares() if hasattr(votacao, 'get_total_votos_populares') else 0
    
    context = {
        'votacao': votacao,
        'total_votos': total_votos,
        'title': f'Editar Votação: {votacao.titulo[:50]}...'
    }
    
    return render(request, 'admin/voting/votacao_edit.html', context)

@staff_member_required
def votacoes_management(request):
    """
    Manage voting sessions - activate/deactivate, view statistics
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        votacao_id = request.POST.get('votacao_id')
        
        if action == 'toggle_active' and votacao_id:
            try:
                votacao = VotacaoDisponivel.objects.get(id=votacao_id)
                votacao.ativo = not votacao.ativo
                votacao.save()
                status = "ativada" if votacao.ativo else "desativada"
                messages.success(request, f'Votação "{votacao.titulo}" foi {status} com sucesso.')
            except VotacaoDisponivel.DoesNotExist:
                messages.error(request, 'Votação não encontrada.')
        
        elif action == 'create_votacao':
            proposicao_id = request.POST.get('proposicao_id')
            titulo = request.POST.get('titulo')
            resumo = request.POST.get('resumo')
            
            if proposicao_id and titulo:
                try:
                    proposicao = Proposicao.objects.get(id=proposicao_id)
                    votacao = VotacaoDisponivel.objects.create(
                        proposicao=proposicao,
                        titulo=titulo,
                        resumo=resumo or f"Votação sobre {proposicao.titulo}",
                        data_hora_votacao=timezone.now(),
                        no_ar_desde=timezone.now(),
                        ativo=True
                    )
                    messages.success(request, f'Votação "{votacao.titulo}" criada com sucesso.')
                except Proposicao.DoesNotExist:
                    messages.error(request, 'Proposição não encontrada.')
    
    votacoes = VotacaoDisponivel.objects.select_related('proposicao').order_by('-created_at')
    proposicoes_sem_votacao = Proposicao.objects.filter(votacaodisponivel__isnull=True)[:20]
    
    context = {
        'votacoes': votacoes,
        'proposicoes_sem_votacao': proposicoes_sem_votacao,
    }
    
    return render(request, 'admin/voting/votacoes_management.html', context)

@staff_member_required
def votacao_create(request):
    """Dedicated page to create a new votação, with optional prefill by proposição."""
    if request.method == 'POST':
        proposicao_id = request.POST.get('proposicao_id')
        titulo = request.POST.get('titulo')
        resumo = request.POST.get('resumo')
        data_hora_votacao = request.POST.get('data_hora_votacao')
        no_ar_desde = request.POST.get('no_ar_desde')
        no_ar_ate = request.POST.get('no_ar_ate')
        ativo = request.POST.get('ativo') == 'on'
        sim_oficial = request.POST.get('sim_oficial')
        nao_oficial = request.POST.get('nao_oficial')

        if proposicao_id and titulo:
            try:
                proposicao = Proposicao.objects.get(id=proposicao_id)

                # Parse datetimes, default to now if invalid or missing
                try:
                    dt_voto = timezone.datetime.fromisoformat(data_hora_votacao.replace('T', ' ')) if data_hora_votacao else timezone.now()
                except Exception:
                    dt_voto = timezone.now()
                try:
                    dt_desde = timezone.datetime.fromisoformat(no_ar_desde.replace('T', ' ')) if no_ar_desde else timezone.now()
                except Exception:
                    dt_desde = timezone.now()
                try:
                    dt_ate = timezone.datetime.fromisoformat(no_ar_ate.replace('T', ' ')) if no_ar_ate else None
                except Exception:
                    dt_ate = None

                # Parse integers
                try:
                    sim_of = int(sim_oficial or 0)
                except ValueError:
                    sim_of = 0
                try:
                    nao_of = int(nao_oficial or 0)
                except ValueError:
                    nao_of = 0

                votacao = VotacaoDisponivel.objects.create(
                    proposicao=proposicao,
                    titulo=titulo,
                    resumo=resumo or f"Votação sobre {proposicao.titulo}",
                    data_hora_votacao=dt_voto,
                    no_ar_desde=dt_desde,
                    no_ar_ate=dt_ate,
                    ativo=ativo,
                    sim_oficial=sim_of,
                    nao_oficial=nao_of,
                )
                messages.success(request, f'Votação "{votacao.titulo}" criada com sucesso.')
                return redirect('gerencial:votacao_edit', pk=votacao.pk)
            except Proposicao.DoesNotExist:
                messages.error(request, 'Proposição não encontrada.')
        else:
            messages.error(request, 'Preencha os campos obrigatórios.')

    # Prefill from GET parameters or proposicao id
    prefill = {
        'proposicao_id': '',
        'proposicao_search': '',
        'titulo': '',
        'resumo': '',
        'data_hora_votacao': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        'no_ar_desde': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        'no_ar_ate': '',
        'ativo': True,
        'sim_oficial': 0,
        'nao_oficial': 0,
        'proposicao_display': ''
    }
    proposicao_id = request.GET.get('proposicao_id')
    if proposicao_id:
        try:
            proposicao = Proposicao.objects.get(id=proposicao_id)
            prefill['proposicao_id'] = proposicao.id
            prefill['proposicao_search'] = proposicao.titulo
            prefill['titulo'] = f"Votação: {proposicao.titulo}"
            prefill['resumo'] = (proposicao.ementa or '').strip()
            prefill['proposicao_display'] = f"{proposicao.tipo} {proposicao.numero}/{proposicao.ano} - {proposicao.titulo}"
        except Proposicao.DoesNotExist:
            messages.error(request, 'Proposição para preenchimento não encontrada.')

    context = {
        'prefill': prefill,
    }
    return render(request, 'admin/voting/votacao_create.html', context)

@staff_member_required
def users_management(request):
    """
    Manage users - view statistics, change user details
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        if action == 'toggle_active' and user_id:
            try:
                user = User.objects.get(id=user_id)
                user.is_active = not user.is_active
                user.save()
                status = "ativado" if user.is_active else "desativado"
                messages.success(request, f'Usuário "{user.username}" foi {status} com sucesso.')
            except User.DoesNotExist:
                messages.error(request, 'Usuário não encontrado.')
    
    users_stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'users_with_votes': User.objects.filter(voto__isnull=False).distinct().count(),
        'recent_users': User.objects.order_by('-date_joined')[:10],
        'top_voters': User.objects.annotate(
            vote_count=Count('voto')
        ).filter(vote_count__gt=0).order_by('-vote_count')[:10],
    }
    
    return render(request, 'admin/voting/users_management.html', {'stats': users_stats})

@staff_member_required
def data_import_export(request):
    """
    Tools for importing and exporting data
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Simulate processing time for demonstration
        time.sleep(2)  # Remove this in production
        
        # Export actions
        if action == 'export_proposicoes':
            # This would implement data export functionality
            message = 'Funcionalidade de exportação será implementada em breve.'
            if is_ajax:
                return JsonResponse({'success': True, 'message': message})
            messages.info(request, message)
        
        elif action == 'import_congressmen':
            # This would implement congressman import functionality
            message = 'Funcionalidade de importação será implementada em breve.'
            if is_ajax:
                return JsonResponse({'success': True, 'message': message})
            messages.info(request, message)
        
        elif action == 'import_dados_index':
            try:
                # Import data from dadosIndex.txt file
                import json
                import re
                from bs4 import BeautifulSoup
                
                dados_index_path = r'C:\Users\User\Dados\Tecnicos\HardESoftware\EmDesenvolvimento\VotoBomPython\00_VB_php\direct\admin\dadosIndex.txt'
                
                with open(dados_index_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    # Extract JSON data from the JavaScript variable assignment
                    json_match = re.search(r'dados = (\[.*\]);', content, re.DOTALL)
                    if not json_match:
                        raise ValueError('Formato de dados inválido no arquivo dadosIndex.txt')
                    
                    dados = json.loads(json_match.group(1))
                
                imported_count = 0
                updated_count = 0
                errors = []
                
                for item in dados:
                    try:
                        id_proposicao = int(item['idProposicao'])
                        votacao_html = item['Votacao']
                        
                        # Parse HTML content to extract structured data
                        soup = BeautifulSoup(votacao_html, 'html.parser')
                        li_items = soup.find_all('li')
                        
                        data = {}
                        for li in li_items:
                            text = li.get_text()
                            if text.startswith('Ementa: '):
                                data['ementa'] = text[8:].strip()
                            elif text.startswith('Numero/ano: '):
                                numero_ano = text[12:].strip()
                                if '/' in numero_ano:
                                    numero, ano = numero_ano.split('/')
                                    data['numero'] = int(numero)
                                    data['ano'] = int(ano)
                            elif text.startswith('Situacao: '):
                                data['situacao'] = text[10:].strip()
                            elif text.startswith('Título: '):
                                data['titulo'] = text[8:].strip()
                            elif text.startswith('Resumo: '):
                                data['resumo'] = text[8:].strip()
                            elif text.startswith('Pergunta: '):
                                data['pergunta'] = text[10:].strip()
                            elif text.startswith('Indexacao: '):
                                data['indexacao'] = text[11:].strip()
                        
                        # Create or update Proposicao
                        proposicao, created = Proposicao.objects.get_or_create(
                            id_proposicao=id_proposicao,
                            defaults={
                                'titulo': data.get('titulo', f'Proposição {id_proposicao}'),
                                'ementa': data.get('ementa', ''),
                                'tipo': 'PL',  # Default type, could be extracted from titulo if needed
                                'numero': data.get('numero', 0),
                                'ano': data.get('ano', 2024),
                                'estado': data.get('situacao', ''),
                            }
                        )
                        
                        if created:
                            imported_count += 1
                        else:
                            # Update existing proposition with new data
                            if data.get('titulo'):
                                proposicao.titulo = data['titulo']
                            if data.get('ementa'):
                                proposicao.ementa = data['ementa']
                            if data.get('numero'):
                                proposicao.numero = data['numero']
                            if data.get('ano'):
                                proposicao.ano = data['ano']
                            if data.get('situacao'):
                                proposicao.estado = data['situacao']
                            proposicao.save()
                            updated_count += 1
                        
                        # Create VotacaoDisponivel if we have voting data
                        if data.get('resumo') or data.get('pergunta'):
                            votacao, votacao_created = VotacaoDisponivel.objects.get_or_create(
                                proposicao=proposicao,
                                defaults={
                                    'titulo': data.get('titulo', f'Votação da Proposição {id_proposicao}'),
                                    'resumo': data.get('resumo', data.get('pergunta', '')),
                                    'data_hora_votacao': timezone.now(),
                                    'no_ar_desde': timezone.now(),
                                    'ativo': True,
                                }
                            )
                            
                            if not votacao_created and data.get('resumo'):
                                votacao.resumo = data['resumo']
                                votacao.save()
                    
                    except Exception as e:
                        errors.append(f'Erro ao processar proposição {item.get("idProposicao", "desconhecida")}: {str(e)}')
                        continue
                
                if errors:
                    error_summary = f'Importação concluída com {len(errors)} erros. '
                    if len(errors) <= 3:
                        error_summary += f'Erros: {"; ".join(errors)}'
                    else:
                        error_summary += f'Primeiros erros: {"; ".join(errors[:3])}...'
                    
                    message = f'Dados importados: {imported_count} novas proposições, {updated_count} atualizadas. {error_summary}'
                    if is_ajax:
                        return JsonResponse({'success': True, 'message': message})
                    messages.warning(request, message)
                else:
                    message = f'Importação concluída com sucesso! {imported_count} novas proposições importadas, {updated_count} atualizadas.'
                    if is_ajax:
                        return JsonResponse({'success': True, 'message': message})
                    messages.success(request, message)
                    
            except FileNotFoundError:
                error_message = 'Arquivo dadosIndex.txt não encontrado no caminho especificado.'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
            except Exception as e:
                error_message = f'Erro ao importar dados: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        # Maintenance actions
        elif action == 'sync_camara':
            try:
                # Simulate synchronization with Câmara dos Deputados API
                # In a real implementation, this would call external APIs
                message = 'Sincronização com dados da Câmara iniciada com sucesso. Processo pode levar alguns minutos.'
                if is_ajax:
                    return JsonResponse({'success': True, 'message': message})
                messages.success(request, message)
                # Here you would implement the actual sync logic
            except Exception as e:
                error_message = f'Erro ao sincronizar dados: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        elif action == 'clear_cache':
            try:
                # Clear Django cache
                from django.core.cache import cache
                cache.clear()
                message = 'Cache do sistema limpo com sucesso.'
                if is_ajax:
                    return JsonResponse({'success': True, 'message': message})
                messages.success(request, message)
            except Exception as e:
                error_message = f'Erro ao limpar cache: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        elif action == 'verify_integrity':
            try:
                # Perform data integrity checks
                issues = []
                
                # Check for propositions without required fields
                proposicoes_sem_titulo = Proposicao.objects.filter(titulo__isnull=True).count()
                if proposicoes_sem_titulo > 0:
                    issues.append(f'{proposicoes_sem_titulo} proposições sem título')
                
                # Check for votes without valid users
                votos_invalidos = Voto.objects.filter(user__isnull=True).count()
                if votos_invalidos > 0:
                    issues.append(f'{votos_invalidos} votos sem usuário válido')
                
                # Check for active votations without propositions
                votacoes_sem_proposicao = VotacaoDisponivel.objects.filter(proposicao__isnull=True).count()
                if votacoes_sem_proposicao > 0:
                    issues.append(f'{votacoes_sem_proposicao} votações sem proposição')
                
                if issues:
                    message = f'Problemas de integridade encontrados: {", ".join(issues)}'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': message})
                    messages.warning(request, message)
                else:
                    message = 'Verificação de integridade concluída. Nenhum problema encontrado.'
                    if is_ajax:
                        return JsonResponse({'success': True, 'message': message})
                    messages.success(request, message)
                    
            except Exception as e:
                error_message = f'Erro ao verificar integridade: {str(e)}'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
        
        else:
            error_message = 'Ação não reconhecida.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': error_message})
            messages.error(request, error_message)
            
        if not is_ajax:
            return redirect('gerencial:data_import_export')
    
    context = {
        'export_options': [
            {'name': 'Proposições', 'action': 'export_proposicoes'},
            {'name': 'Votações', 'action': 'export_votacoes'},
            {'name': 'Votos Populares', 'action': 'export_votos'},
        ],
        'import_options': [
            {'name': 'Dados Index (dadosIndex.txt)', 'action': 'import_dados_index'},
            {'name': 'Congressistas', 'action': 'import_congressmen'},
            {'name': 'Proposições', 'action': 'import_proposicoes'},
            {'name': 'Votações Oficiais', 'action': 'import_votacoes'},
        ],
    }
    
    return render(request, 'admin/voting/data_import_export.html', context)

@staff_member_required
def proposicao_add(request):
    """
    Add a new proposition
    """
    if request.method == 'POST':
        # Get form data
        titulo = request.POST.get('titulo', '').strip()
        ementa = request.POST.get('ementa', '').strip()
        tipo = request.POST.get('tipo', '').strip().upper()
        numero = request.POST.get('numero', '').strip()
        ano = request.POST.get('ano', '').strip()
        estado = request.POST.get('estado', '').strip()
        id_proposicao = request.POST.get('id_proposicao', '').strip()
        
        # Validate required fields
        if not all([titulo, tipo, numero, ano]):
            messages.error(request, 'Título, tipo, número e ano são obrigatórios.')
        else:
            try:
                # Convert numeric fields
                numero = int(numero)
                ano = int(ano)
                
                # Check if proposition already exists
                if Proposicao.objects.filter(tipo=tipo, numero=numero, ano=ano).exists():
                    messages.error(request, f'Proposição {tipo} {numero}/{ano} já existe no sistema.')
                else:
                    # Create new proposition
                    proposicao = Proposicao.objects.create(
                        titulo=titulo,
                        ementa=ementa,
                        tipo=tipo,
                        numero=numero,
                        ano=ano,
                        estado=estado,
                        id_proposicao=id_proposicao if id_proposicao else None
                    )
                    
                    messages.success(request, f'Proposição {tipo} {numero}/{ano} criada com sucesso!')
                    return redirect('gerencial:proposicao_edit', pk=proposicao.pk)
                    
            except ValueError:
                messages.error(request, 'Número e ano devem ser valores numéricos válidos.')
            except Exception as e:
                messages.error(request, f'Erro ao criar proposição: {str(e)}')
    
    # Get current year as default
    from datetime import datetime
    current_year = datetime.now().year
    
    context = {
        'title': 'Adicionar Nova Proposição',
        'current_year': current_year,
    }
    
    return render(request, 'admin/voting/proposicao_add.html', context)


@staff_member_required
def proposicao_import(request):
    """Import a proposição from Câmara by id_proposicao and redirect to edit"""
    context = {
        'title': 'Importar Proposição por ID da Câmara',
    }

    if request.method == 'POST':
        id_proposicao = request.POST.get('id_proposicao', '').strip()
        if not id_proposicao:
            messages.error(request, 'Informe o ID da proposição da Câmara (idProposicao).')
        else:
            try:
                ext_id = int(id_proposicao)
                from .services.camara_api import camara_api

                # Use the service to sync a single proposição by its ID
                try:
                    proposicao = camara_api._sync_single_proposicao({'id': ext_id})
                except Exception as e:
                    messages.error(request, f'Erro ao obter dados da Câmara: {str(e)}')
                    proposicao = None

                if proposicao:
                    messages.success(request, f'Proposição {proposicao.tipo} {proposicao.numero}/{proposicao.ano} importada/atualizada com sucesso!')
                    return redirect('gerencial:proposicao_edit', pk=proposicao.pk)
                else:
                    messages.error(request, 'Não foi possível criar a proposição a partir do ID informado.')
            except ValueError:
                messages.error(request, 'O ID informado deve ser um número inteiro válido.')

    return render(request, 'admin/voting/proposicao_import.html', context)

@staff_member_required
def camara_admin(request):
    """
    Administrative tools for managing Chamber propositions
    Equivalent to vb01c_ProposicoesCamara.php
    """
    from datetime import datetime, timedelta
    import json
    
    context = {
        'title': 'Administrar Proposições da Câmara',
        'current_year': datetime.now().year,
        'default_year': 2017,
        'date_7_days_ago': (datetime.now() - timedelta(days=7)).strftime('%d/%m/%Y'),
        'date_today': datetime.now().strftime('%d/%m/%Y'),
        'date_2_months_ago': (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'),
        'date_today_iso': datetime.now().strftime('%Y-%m-%d'),
        # Default dates for "Listar Proposições por Período" form
        'default_data_inicio': (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),  # One year ago
        'default_data_fim': datetime.now().strftime('%Y-%m-%d'),  # Today
    }
    

    
    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')
        dev_log(f"DEBUG: POST request received with action: {action}")
        dev_log(f"DEBUG: All POST data: {dict(request.POST)}")
        
        if action == 'exibeUltimaProposicao':
            # Show last proposition inserted
            try:
                ultima_proposicao = Proposicao.objects.latest('id')
                context['ultima_proposicao'] = ultima_proposicao
                context['action_result'] = 'ultima_proposicao'
            except Proposicao.DoesNotExist:
                context['error'] = 'Nenhuma proposição encontrada no banco de dados.'
                
        elif action == 'exibeEstatisticaProposicoesPriInseridas':
            # Show proposition statistics
            from django.db.models import Count
            stats = {
                'total': Proposicao.objects.count(),
                'por_tipo': list(Proposicao.objects.values('tipo').annotate(count=Count('id')).order_by('-count')),
                'por_ano': list(Proposicao.objects.values('ano').annotate(count=Count('id')).order_by('-ano')),
                'por_estado': list(Proposicao.objects.values('estado').annotate(count=Count('id')).order_by('-count')),
            }
            context['stats'] = stats
            context['action_result'] = 'estatisticas'
            
        elif action == 'listarProposicoesVotadas':
            # List propositions that have been voted
            proposicoes_votadas = Proposicao.objects.filter(
                votacaodisponivel__isnull=False
            ).distinct().order_by('-ano', '-numero')[:50]
            context['proposicoes_votadas'] = proposicoes_votadas
            context['action_result'] = 'proposicoes_votadas'
            
        elif action == 'listarVotacoesDisponiveis':
            # List available votings
            votacoes = VotacaoDisponivel.objects.filter(ativo=True).order_by('-data_hora_votacao')[:50]
            context['votacoes_disponiveis'] = votacoes
            context['action_result'] = 'votacoes_disponiveis'
            
        elif action == 'atualizarProposicoesVotadasPlenario':
            # Update propositions voted in plenary for specific date range
            data_inicial = request.POST.get('dataInicial')
            data_final = request.POST.get('dataFinal')
            try:
                if not data_inicial or not data_final:
                    raise ValueError("Data inicial e final são obrigatórias")
                
                from .services.camara_api import camara_api
                stats = camara_api.sync_proposicoes_by_date_range(data_inicial, data_final)
                context['update_result'] = f'Sincronização do período {data_inicial} a {data_final}: {stats["created"]} criadas, {stats["updated"]} atualizadas, {stats["errors"]} erros.'
                context['action_result'] = 'update_result'
                messages.success(request, f'Sincronização concluída: {stats["created"]} proposições criadas')
            except ValueError as e:
                context['error'] = f'Erro de validação: {str(e)}'
            except Exception as e:
                context['error'] = f'Erro na sincronização: {str(e)}'
                
        elif action == 'cadastrarEmentasFaltantes':
            # Register missing ementas
            try:
                from .services.camara_api import camara_api
                updated_count = camara_api.update_missing_ementas()
                context['ementas_result'] = f'Atualizadas {updated_count} ementas faltantes com sucesso.'
                context['action_result'] = 'ementas_result'
                messages.success(request, f'Atualizadas {updated_count} ementas')
            except Exception as e:
                context['error'] = f'Erro ao atualizar ementas: {str(e)}'
                
        elif action == 'loopObterVotacoes':
            # Loop to get votings for propositions
            ano = request.POST.get('anoVotacao', datetime.now().year)
            try:
                ano = int(ano)
                from .services.camara_api import camara_api
                proposicoes = Proposicao.objects.filter(ano=ano)[:20]  # Limit for performance
                total_votacoes = 0
                
                for proposicao in proposicoes:
                    if proposicao.id_proposicao:
                        votacoes_count = camara_api.sync_votacoes_for_proposicao(proposicao)
                        total_votacoes += votacoes_count
                
                context['loop_result'] = f'Sincronizadas {total_votacoes} votações para {proposicoes.count()} proposições do ano {ano}.'
                context['action_result'] = 'loop_result'
                messages.success(request, f'Sincronizadas {total_votacoes} votações')
            except ValueError:
                context['error'] = 'Ano inválido fornecido.'
            except Exception as e:
                context['error'] = f'Erro na sincronização de votações: {str(e)}'
                
        elif action == 'atualizarNProposicoes':
            # Update N propositions starting from a specific one
            n_proposicoes = request.POST.get('nProximasProposicoes', 1)
            partir_da = request.POST.get('aPartirDaProposicao', '')
            tempo_max = request.POST.get('tempoMaximoProcess', 150)
            
            try:
                n_proposicoes = int(n_proposicoes)
                tempo_max = int(tempo_max)
                
                from .services.camara_api import camara_api
                proposicoes_api = camara_api.get_recent_proposicoes(days=30)[:n_proposicoes]
                created_count = 0
                updated_count = 0
                
                for prop_data in proposicoes_api:
                    try:
                        result = camara_api._sync_single_proposicao(prop_data)
                        if result['created']:
                            created_count += 1
                        else:
                            updated_count += 1
                    except Exception:
                        continue
                
                context['update_n_result'] = f'Processadas {n_proposicoes} proposições: {created_count} criadas, {updated_count} atualizadas.'
                context['action_result'] = 'update_n_result'
                messages.success(request, f'Processadas {created_count + updated_count} proposições')
            except ValueError:
                context['error'] = 'Valores numéricos inválidos fornecidos.'
            except Exception as e:
                context['error'] = f'Erro ao atualizar proposições: {str(e)}'
                
        elif action == 'listarProposicoesTramitacao':
            # List propositions in processing within date range
            data_inicio = request.POST.get('dataInicio')
            data_fim = request.POST.get('dataFim')
            api_type = request.POST.get('apiType', 'producao')
            
            try:
                from .services.camara_api import camara_api
                
                if not data_inicio or not data_fim:
                    # Default to last 30 days
                    data_fim = datetime.now().strftime('%Y-%m-%d')
                    data_inicio = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                
                proposicoes = camara_api.get_proposicoes_by_date_range(data_inicio, data_fim)
                context['tramitacao_result'] = {
                    'proposicoes': proposicoes[:50],  # Limit for display
                    'total': len(proposicoes),
                    'data_inicio': data_inicio,
                    'data_fim': data_fim,
                    'api_type': api_type
                }
                context['action_result'] = 'tramitacao_result'
                messages.success(request, f'Encontradas {len(proposicoes)} proposições tramitando entre {data_inicio} e {data_fim}')
            except Exception as e:
                context['error'] = f'Erro ao listar proposições em tramitação: {str(e)}'
    
    # Get last proposition ID for JavaScript
    try:
        ultima_proposicao_id = Proposicao.objects.latest('id').id_proposicao or Proposicao.objects.latest('id').id
        context['ultima_proposicao_id'] = ultima_proposicao_id
    except Proposicao.DoesNotExist:
        context['ultima_proposicao_id'] = 0
    
    return render(request, 'admin/voting/camara_admin.html', context)


@staff_member_required
def ajax_proposicao_search(request):
    """
    AJAX endpoint for searching propositions
    """
    query = request.GET.get('q', '')
    if len(query) < 3:
        return JsonResponse({'results': []})
    
    proposicoes = Proposicao.objects.filter(
        Q(titulo__icontains=query) | 
        Q(ementa__icontains=query) |
        Q(id_proposicao__icontains=query)
    )[:20]
    
    results = [
        {
            'id': p.id,
            'text': f"{p.tipo} {p.numero}/{p.ano} - {p.titulo}",
            'id_proposicao': p.id_proposicao,
        }
        for p in proposicoes
    ]
    
    return JsonResponse({'results': results})

@staff_member_required
def ajax_proposicao_votacoes(request):
    """Cache-first endpoint: retorna votações por proposição.
    1) Se existir em ProposicaoVotacao, retorna do banco.
    2) Caso contrário, consulta API da Câmara, filtra, insere em ProposicaoVotacao e retorna.
    """
    prop_id = request.GET.get('proposicao_id')
    if not prop_id:
        return JsonResponse({'ok': False, 'error': 'Parâmetro proposicao_id é obrigatório.'}, status=400)
    try:
        prop_id_int = int(prop_id)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'proposicao_id deve ser numérico.'}, status=400)

    # Tenta localizar/garantir Proposicao
    proposicao = Proposicao.objects.filter(id_proposicao=prop_id_int).first()
    if proposicao is None:
        # Buscar detalhes mínimos para criar Proposicao e poder relacionar
        try:
            details = camara_api.get_proposicao_details(prop_id_int) or {}
            dados = details.get('dados') or {}
            # Campos obrigatórios
            titulo = (dados.get('ementa') or '')[:500]
            ementa = dados.get('ementa') or ''
            tipo = dados.get('siglaTipo') or ''
            numero = int(dados.get('numero') or 0)
            ano = int(dados.get('ano') or 0)
            autor = ''
            estado = dados.get('statusProposicao', {}).get('descricaoSituacao') or ''
            proposicao = Proposicao.objects.create(
                id_proposicao=prop_id_int,
                titulo=titulo,
                ementa=ementa,
                tipo=tipo,
                numero=numero,
                ano=ano,
                autor=autor,
                estado=estado,
            )
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Falha ao garantir proposição: {e}'}, status=500)

    # 1) Consulta cache local
    cached = list(ProposicaoVotacao.objects.filter(proposicao=proposicao).order_by('votacao_sufixo'))
    if cached:
        dados = [
            {
                'id': f"{prop_id_int}-{pv.votacao_sufixo}",
                'descricao': pv.descricao or '',
                'dataHora': '',
                'resultado': '',
            }
            for pv in cached
        ]
        return JsonResponse({'ok': True, 'source': 'db', 'dados': dados})

    # 2) Fallback: Câmara API
    try:
        api_url = f"{CamaraAPIService.BASE_URL}/proposicoes/{prop_id_int}/votacoes"
        api_items = camara_api.get_proposicao_votacoes(prop_id_int) or []
        # Filtro por descrição contendo chaves relevantes (case-insensitive)
        needles = [
            'em primeiro turno',
            'em segundo turno',
            'emenda aglutinativa',
        ]
        def _desc(item):
            return (item.get('descricao') or item.get('descrição') or '').lower()
        filtered = [i for i in api_items if any(n in _desc(i) for n in needles)]

        # Inserir no cache local
        to_create = []
        for item in filtered:
            full_id = item.get('id') or item.get('idVotacao') or ''
            sufixo = None
            try:
                if isinstance(full_id, str) and '-' in full_id:
                    sufixo = int(full_id.split('-')[-1])
                elif isinstance(full_id, int):
                    # Em alguns casos a API pode devolver sufixo isolado
                    sufixo = full_id
            except Exception:
                sufixo = None
            if sufixo is None:
                continue
            to_create.append(ProposicaoVotacao(
                proposicao=proposicao,
                votacao_sufixo=sufixo,
                descricao=item.get('descricao') or item.get('descrição') or '',
            ))

        # Evitar conflitos com unique_together
        try:
            with transaction.atomic():
                ProposicaoVotacao.objects.bulk_create(to_create, ignore_conflicts=True)
        except Exception:
            pass

        dados = [
            {
                'id': (item.get('id') or item.get('idVotacao') or ''),
                'descricao': item.get('descricao') or item.get('descrição') or '',
                'dataHora': item.get('dataHoraRegistro') or item.get('dataHora') or '',
                'resultado': item.get('resultado') or '',
            }
            for item in filtered
        ]
        return JsonResponse({'ok': True, 'source': 'api', 'dados': dados})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Erro ao consultar API: {e}', 'api_url': api_url}, status=502)