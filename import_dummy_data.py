#!/usr/bin/env python
"""
Script to import dummy data from dadosIndex.txt into the Django database.
This script parses the JavaScript array format and creates Proposicao and VotacaoDisponivel objects.
"""

import os
import sys
import django
import json
import re
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings')
django.setup()

from voting.models import Proposicao, VotacaoDisponivel
from django.db import transaction

def parse_html_content(html_content):
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

def clean_text(text):
    """Clean HTML entities and formatting from text"""
    if not text:
        return ""
    
    # Replace HTML entities
    text = text.replace('\\u00e7', 'ç')
    text = text.replace('\\u00e3', 'ã')
    text = text.replace('\\u00e1', 'á')
    text = text.replace('\\u00e9', 'é')
    text = text.replace('\\u00ed', 'í')
    text = text.replace('\\u00f3', 'ó')
    text = text.replace('\\u00fa', 'ú')
    text = text.replace('\\u00ea', 'ê')
    text = text.replace('\\u00f4', 'ô')
    text = text.replace('\\u00e2', 'â')
    text = text.replace('\\u00f5', 'õ')
    text = text.replace('\\u00fc', 'ü')
    text = text.replace('\\u00e0', 'à')
    text = text.replace('\\u00c7', 'Ç')
    text = text.replace('\\u00c1', 'Á')
    text = text.replace('\\u00c9', 'É')
    text = text.replace('\\u00cd', 'Í')
    text = text.replace('\\u00d3', 'Ó')
    text = text.replace('\\u00da', 'Ú')
    text = text.replace('\\u00ca', 'Ê')
    text = text.replace('\\u00d4', 'Ô')
    text = text.replace('\\u00c2', 'Â')
    text = text.replace('\\u00d5', 'Õ')
    text = text.replace('\\u00dc', 'Ü')
    text = text.replace('\\u00c0', 'À')
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def determine_tipo_from_data(data):
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

def import_dummy_data():
    """Import dummy data from dadosIndex.txt"""
    
    # Read the data file
    data_file_path = 'C:/Users/User/Dados/Tecnicos/HardESoftware/EmDesenvolvimento/VotoBomPython/00_VB_php/direct/admin/dadosIndex.txt'
    
    try:
        with open(data_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"Error: File not found at {data_file_path}")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Extract the JavaScript array
    match = re.search(r'dados = (\[.*\]);', content, re.DOTALL)
    if not match:
        print("Error: Could not find 'dados' array in the file")
        return
    
    json_str = match.group(1)
    
    try:
        # Parse the JSON data
        data_list = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return
    
    print(f"Found {len(data_list)} records to import")
    
    created_proposicoes = 0
    created_votacoes = 0
    errors = 0
    
    with transaction.atomic():
        for item in data_list:
            try:
                id_proposicao = int(item['idProposicao'])
                votacao_html = item['Votacao']
                
                # Parse the HTML content
                parsed_data = parse_html_content(votacao_html)
                
                # Clean the text data
                ementa = clean_text(parsed_data.get('ementa', ''))
                titulo = clean_text(parsed_data.get('titulo', ''))
                estado = clean_text(parsed_data.get('estado', ''))
                resumo = clean_text(parsed_data.get('resumo', ''))
                
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
                        'tipo': determine_tipo_from_data(parsed_data),
                        'numero': parsed_data.get('numero', id_proposicao % 10000),
                        'ano': parsed_data.get('ano', 2016),
                        'estado': estado,
                    }
                )
                
                if created:
                    created_proposicoes += 1
                    print(f"Created Proposicao: {proposicao}")
                
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
                        print(f"Created VotacaoDisponivel: {votacao}")
                
            except Exception as e:
                errors += 1
                print(f"Error processing record {item.get('idProposicao', 'unknown')}: {e}")
                continue
    
    print(f"\nImport completed:")
    print(f"- Created {created_proposicoes} proposições")
    print(f"- Created {created_votacoes} votações disponíveis")
    print(f"- Errors: {errors}")

if __name__ == '__main__':
    print("Starting dummy data import...")
    import_dummy_data()
    print("Import finished.")