from django.shortcuts import render, redirect
from django.views.generic import TemplateView, View
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)

class HomeView(TemplateView):
    """Landing page view - equivalent to index_final.php"""
    template_name = 'home/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'VoteBem - Vote como um deputado e veja quem te representa'
        return context

@method_decorator(csrf_exempt, name='dispatch')
class NewsletterSignupView(View):
    """Handle newsletter email signup - equivalent to the malaDireta functionality"""
    
    def post(self, request):
        try:
            # Parse JSON data from request body
            data = json.loads(request.body.decode('utf-8'))
            
            # Extract name and email from the serialized form data
            form_data = {}
            for item in data:
                form_data[item['name']] = item['value']
            
            nome = form_data.get('nome', '').strip()
            email = form_data.get('email', '').strip()
            
            if not nome or not email:
                return JsonResponse({
                    'success': False, 
                    'message': 'Nome e email são obrigatórios'
                }, status=400)
            
            # Here you would typically save to database
            # For now, we'll just log it and send a confirmation email
            logger.info(f"Newsletter signup: {nome} <{email}>")
            
            # Send confirmation email (optional)
            try:
                send_mail(
                    subject='Bem-vindo ao VoteBem!',
                    message=f'Olá {nome},\n\nObrigado por se cadastrar em nossa newsletter!\n\nEquipe VoteBem',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.warning(f"Failed to send confirmation email: {e}")
            
            return JsonResponse({
                'success': True,
                'message': 'Email cadastrado com sucesso!'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados inválidos'
            }, status=400)
        except Exception as e:
            logger.error(f"Newsletter signup error: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Erro interno do servidor'
            }, status=500)

class ContactView(TemplateView):
    """Contact page view"""
    template_name = 'home/contact.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Contato - VoteBem'
        return context
