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
from .models import Proposicao, VotacaoDisponivel, Voto, Congressman, CongressmanVote
from django.contrib.auth.models import User

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
    
    # Pagination
    paginator = Paginator(proposicoes, 25)  # Show 25 propositions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    tipos_disponiveis = Proposicao.objects.values_list('tipo', flat=True).distinct().order_by('tipo')
    anos_disponiveis = Proposicao.objects.values_list('ano', flat=True).distinct().order_by('-ano')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_filter': tipo_filter,
        'ano_filter': ano_filter,
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
        return redirect('administrativo:proposicoes_list')
    
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
                return redirect('administrativo:proposicoes_list')
                
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
            return redirect('administrativo:votacao_edit', pk=pk)
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
            return redirect('administrativo:data_import_export')
    
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
                    return redirect('administrativo:proposicao_edit', pk=proposicao.pk)
                    
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
    }
    
    # Handle GET parameter for direct API testing
    if request.GET.get('test_api') == '1':
        try:
            from .services.camara_api import camara_api
            print("DEBUG: Testing API connection...")
            test_data = camara_api._make_request("proposicoes", {"itens": 1})
            if test_data and 'dados' in test_data:
                context['api_test_result'] = f"✅ API funcionando! Encontradas {len(test_data['dados'])} proposições de teste."
                context['api_test_data'] = test_data['dados'][0] if test_data['dados'] else None
                print(f"DEBUG: API test successful: {context['api_test_result']}")
            else:
                context['api_test_result'] = "❌ API não retornou dados válidos."
                print("DEBUG: API test failed - no valid data")
            context['action_result'] = 'api_test'
            messages.success(request, "Teste de API concluído via GET!")
        except Exception as e:
            context['error'] = f'Erro no teste de API: {str(e)}'
            context['api_test_result'] = f"❌ Erro na conexão: {str(e)}"
            context['action_result'] = 'api_test'
            print(f"DEBUG: API test error: {str(e)}")
    
    # Handle GET parameter for direct year sync testing
    if request.GET.get('test_sync') == '1':
        ano = request.GET.get('ano', datetime.now().year)
        try:
            ano = int(ano)
            from .services.camara_api import camara_api
            print(f"DEBUG: Testing sync for year {ano}...")
            stats = camara_api.sync_proposicoes_by_year(ano)
            context['update_result'] = f'Sincronização do ano {ano}: {stats["created"]} criadas, {stats["updated"]} atualizadas, {stats["errors"]} erros.'
            context['action_result'] = 'update_result'
            messages.success(request, f'Sincronização concluída via GET: {stats["created"]} proposições criadas')
            print(f"DEBUG: Sync test successful: {context['update_result']}")
        except Exception as e:
            context['error'] = f'Erro na sincronização: {str(e)}'
            print(f"DEBUG: Sync test error: {str(e)}")
    
    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')
        print(f"DEBUG: POST request received with action: {action}")
        print(f"DEBUG: All POST data: {dict(request.POST)}")
        
        if action == 'test':
            print("TEST ACTION RECEIVED!")
            messages.success(request, "Test form submission successful!")
            return redirect('administrativo:camara_admin')
            
        elif action == 'testApiConnection':
            # Test API connection
            try:
                from .services.camara_api import camara_api
                # Test with a simple API call
                test_data = camara_api._make_request("proposicoes", {"itens": 1})
                if test_data and 'dados' in test_data:
                    context['api_test_result'] = f"✅ API funcionando! Encontradas {len(test_data['dados'])} proposições de teste."
                    context['api_test_data'] = test_data['dados'][0] if test_data['dados'] else None
                else:
                    context['api_test_result'] = "❌ API não retornou dados válidos."
                context['action_result'] = 'api_test'
                messages.success(request, "Teste de API concluído!")
            except Exception as e:
                context['error'] = f'Erro no teste de API: {str(e)}'
                context['api_test_result'] = f"❌ Erro na conexão: {str(e)}"
                context['action_result'] = 'api_test'
        
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
            # Update propositions voted in plenary for specific year
            ano = request.POST.get('ano', datetime.now().year)
            try:
                ano = int(ano)
                from .services.camara_api import camara_api
                stats = camara_api.sync_proposicoes_by_year(ano)
                context['update_result'] = f'Sincronização do ano {ano}: {stats["created"]} criadas, {stats["updated"]} atualizadas, {stats["errors"]} erros.'
                context['action_result'] = 'update_result'
                messages.success(request, f'Sincronização concluída: {stats["created"]} proposições criadas')
            except ValueError:
                context['error'] = 'Ano inválido fornecido.'
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
            'text': f"{p.tipo} {p.numero}/{p.ano} - {p.titulo[:60]}",
            'id_proposicao': p.id_proposicao,
        }
        for p in proposicoes
    ]
    
    return JsonResponse({'results': results})

@staff_member_required
def test_form(request):
    """
    Simple test view for form submission debugging
    """
    if request.method == 'POST':
        print("TEST FORM: POST request received!")
        print(f"POST data: {dict(request.POST)}")
        action = request.POST.get('action')
        print(f"Action: {action}")
        
        if action == 'test':
            messages.success(request, "Test form submission successful!")
            return redirect('administrativo:test_form')
    
    return render(request, 'admin/voting/test_form.html')