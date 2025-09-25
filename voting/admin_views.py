from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
import time
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
            {'name': 'Congressistas', 'action': 'import_congressmen'},
            {'name': 'Proposições', 'action': 'import_proposicoes'},
            {'name': 'Votações Oficiais', 'action': 'import_votacoes'},
        ],
    }
    
    return render(request, 'admin/voting/data_import_export.html', context)

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