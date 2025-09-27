"""
Django management command to import dummy data from dadosIndex.txt into the database.
This command parses the JavaScript array format and creates Proposicao and VotacaoDisponivel objects.
"""

import json
import re
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from voting.models import Proposicao, VotacaoDisponivel


class Command(BaseCommand):
    help = 'Import dummy data from dadosIndex.txt into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='C:/Users/User/Dados/Tecnicos/HardESoftware/EmDesenvolvimento/VotoBomPython/00_VB_php/direct/admin/dadosIndex.txt',
            help='Path to the dadosIndex.txt file'
        )

    def parse_html_content(self, html_content):
        """Parse HTML content to extract structured data"""
        data = {}
        
        # Extract ementa
        ementa_match = re.search(r'<li>Ementa:\s*(.*?)</li>', html_content, re.DOTALL)
        if ementa_match:
            data['ementa'] = ementa_match.group(1).strip()
        
        # Extract numero/ano
        numero_ano_match = re.search(r'<li>Numero/ano:\s*(\d+)/(\d+)</li>', html_content)
        if numero_ano_match:
            data['numero'] = int(numero_ano_match.group(1))
            data['ano'] = int(numero_ano_match.group(2))
        
        # Extract situacao (estado)
        situacao_match = re.search(r'<li>Situacao:\s*(.*?)</li>', html_content)
        if situacao_match:
            data['estado'] = situacao_match.group(1).strip()
        
        # Extract titulo
        titulo_match = re.search(r'<li>Título:\s*(.*?)</li>', html_content)
        if titulo_match:
            data['titulo'] = titulo_match.group(1).strip()
        
        # Extract resumo
        resumo_match = re.search(r'<li>Resumo:\s*(.*?)</li>', html_content, re.DOTALL)
        if resumo_match:
            data['resumo'] = resumo_match.group(1).strip()
        
        # Extract pergunta
        pergunta_match = re.search(r'<li>Pergunta:\s*(.*?)</li>', html_content)
        if pergunta_match:
            data['pergunta'] = pergunta_match.group(1).strip()
        
        # Extract indexacao
        indexacao_match = re.search(r'<li>Indexacao:\s*(.*?)</li>', html_content, re.DOTALL)
        if indexacao_match:
            data['indexacao'] = indexacao_match.group(1).strip()
        
        return data

    def clean_text(self, text):
        """Clean HTML entities and formatting from text"""
        if not text:
            return ""
        
        # Replace HTML entities
        replacements = {
            '\\u00e7': 'ç', '\\u00e3': 'ã', '\\u00e1': 'á', '\\u00e9': 'é',
            '\\u00ed': 'í', '\\u00f3': 'ó', '\\u00fa': 'ú', '\\u00ea': 'ê',
            '\\u00f4': 'ô', '\\u00e2': 'â', '\\u00f5': 'õ', '\\u00fc': 'ü',
            '\\u00e0': 'à', '\\u00c7': 'Ç', '\\u00c1': 'Á', '\\u00c9': 'É',
            '\\u00cd': 'Í', '\\u00d3': 'Ó', '\\u00da': 'Ú', '\\u00ca': 'Ê',
            '\\u00d4': 'Ô', '\\u00c2': 'Â', '\\u00d5': 'Õ', '\\u00dc': 'Ü',
            '\\u00c0': 'À'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def determine_tipo_from_data(self, data):
        """Determine proposition type from the data"""
        if 'ementa' in data:
            ementa = data['ementa'].lower()
            if 'projeto de lei' in ementa:
                return 'PL'
            elif 'proposta de emenda' in ementa:
                return 'PEC'
            elif 'requer' in ementa or 'requerimento' in ementa:
                return 'REQ'
            elif 'medida provisória' in ementa:
                return 'MPV'
        return 'PL'  # Default

    def handle(self, *args, **options):
        data_file_path = options['file']
        
        try:
            with open(data_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except FileNotFoundError:
            raise CommandError(f'File not found at {data_file_path}')
        except Exception as e:
            raise CommandError(f'Error reading file: {e}')
        
        # Extract the JavaScript array
        match = re.search(r'dados = (\[.*\]);', content, re.DOTALL)
        if not match:
            raise CommandError('Could not find "dados" array in the file')
        
        json_str = match.group(1)
        
        try:
            # Parse the JSON data
            data_list = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise CommandError(f'Error parsing JSON: {e}')
        
        self.stdout.write(f'Found {len(data_list)} records to import')
        
        created_proposicoes = 0
        created_votacoes = 0
        errors = 0
        
        with transaction.atomic():
            for item in data_list:
                try:
                    id_proposicao = int(item['idProposicao'])
                    votacao_html = item['Votacao']
                    
                    # Parse the HTML content
                    parsed_data = self.parse_html_content(votacao_html)
                    
                    # Clean the text data
                    ementa = self.clean_text(parsed_data.get('ementa', ''))
                    titulo = self.clean_text(parsed_data.get('titulo', ''))
                    estado = self.clean_text(parsed_data.get('estado', ''))
                    resumo = self.clean_text(parsed_data.get('resumo', ''))
                    
                    # If no title is provided, use a truncated ementa
                    if not titulo and ementa:
                        titulo = ementa[:100] + "..." if len(ementa) > 100 else ementa
                    elif not titulo:
                        titulo = f"Proposição {id_proposicao}"
                    
                    # Get or create Proposicao
                    proposicao, created = Proposicao.objects.get_or_create(
                        id_proposicao=id_proposicao,
                        defaults={
                            'titulo': titulo,
                            'ementa': ementa or f"Ementa da proposição {id_proposicao}",
                            'tipo': self.determine_tipo_from_data(parsed_data),
                            'numero': parsed_data.get('numero', id_proposicao % 10000),
                            'ano': parsed_data.get('ano', 2016),
                            'estado': estado,
                        }
                    )
                    
                    if created:
                        created_proposicoes += 1
                        self.stdout.write(f'Created Proposicao: {proposicao}')
                    
                    # Create VotacaoDisponivel if there's voting data
                    if resumo or parsed_data.get('pergunta'):
                        votacao_titulo = titulo if titulo else f"Votação da Proposição {id_proposicao}"
                        votacao_resumo = resumo if resumo else parsed_data.get('pergunta', f"Votação sobre a proposição {id_proposicao}")
                        
                        # Set voting dates (make them recent for testing)
                        now = timezone.now()
                        data_votacao = now - timedelta(days=30)  # 30 days ago
                        no_ar_desde = now - timedelta(days=7)    # Available for 7 days
                        no_ar_ate = now + timedelta(days=30)     # Available for 30 more days
                        
                        votacao, created = VotacaoDisponivel.objects.get_or_create(
                            proposicao=proposicao,
                            defaults={
                                'titulo': votacao_titulo,
                                'resumo': votacao_resumo,
                                'data_hora_votacao': data_votacao,
                                'no_ar_desde': no_ar_desde,
                                'no_ar_ate': no_ar_ate,
                                'sim_oficial': 0,  # Will be updated with real data later
                                'nao_oficial': 0,
                                'ativo': True,
                            }
                        )
                        
                        if created:
                            created_votacoes += 1
                            self.stdout.write(f'Created VotacaoDisponivel: {votacao}')
                    
                except Exception as e:
                    errors += 1
                    self.stderr.write(f'Error processing record {item.get("idProposicao", "unknown")}: {e}')
                    continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nImport completed:\n'
                f'- Created {created_proposicoes} proposições\n'
                f'- Created {created_votacoes} votações disponíveis\n'
                f'- Errors: {errors}'
            )
        )