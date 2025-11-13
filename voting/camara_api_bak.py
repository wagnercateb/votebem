"""
Brazilian Chamber of Deputies API Integration Service
Handles communication with https://dadosabertos.camara.leg.br API
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from ..models import Proposicao, VotacaoDisponivel
import logging

logger = logging.getLogger(__name__)

class CamaraAPIService:
    """
    Service to interact with Brazilian Chamber of Deputies Open Data API
    """
    
    BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VoteBem/1.0 (Sistema de Votação Popular)',
            'Accept': 'application/json',
        })
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Make a request to the Câmara API
        """
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            print(f"DEBUG: Making request to {url} with params: {params}")
            
            # Add additional headers that might help with 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://dadosabertos.camara.leg.br/',
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            print(f"DEBUG: Response status: {response.status_code}")
            print(f"DEBUG: Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Request error: {e}")
            logger.error(f"Error making request to {url}: {e}")
            raise Exception(f"Erro na comunicação com a API da Câmara: {str(e)}")
        except json.JSONDecodeError as e:
            print(f"DEBUG: JSON decode error: {e}")
            logger.error(f"Error decoding JSON response: {e}")
            raise Exception(f"Erro ao processar resposta da API: {str(e)}")
    
    def get_proposicoes_by_date_range(self, data_inicio: str, data_fim: str, 
                                    ordem: str = "ASC", ordenar_por: str = "id") -> List[Dict]:
        """
        Get propositions that had some activity between two dates
        
        Args:
            data_inicio: Start date in YYYY-MM-DD format
            data_fim: End date in YYYY-MM-DD format
            ordem: ASC or DESC
            ordenar_por: Field to order by (id, dataApresentacao, etc.)
        
        Returns:
            List of propositions
        """
        params = {
            'dataInicio': data_inicio,
            'dataFim': data_fim,
            'ordem': ordem,
            'ordenarPor': ordenar_por,
            'itens': 100  # Maximum items per page
        }
        
        all_proposicoes = []
        page = 1
        
        while True:
            params['pagina'] = page
            try:
                data = self._make_request("proposicoes", params)
                
                if not data or 'dados' not in data:
                    break
                    
                proposicoes = data['dados']
                if not proposicoes:
                    break
                    
                all_proposicoes.extend(proposicoes)
                
                # Check if there are more pages
                links = data.get('links', [])
                has_next = any(link.get('rel') == 'next' for link in links)
                if not has_next:
                    break
                    
                page += 1
                
                # Safety limit to avoid infinite loops
                if page > 50:
                    logger.warning("Reached maximum page limit (50) for API request")
                    break
            except Exception as e:
                # Re-raise the exception to bubble up to the calling method
                raise e
        
        return all_proposicoes
    
    def get_proposicao_details(self, proposicao_id: int) -> Optional[Dict]:
        """
        Get detailed information about a specific proposition
        """
        return self._make_request(f"proposicoes/{proposicao_id}")
    
    def get_proposicao_votacoes(self, proposicao_id: int) -> List[Dict]:
        """
        Get voting information for a specific proposition
        """
        data = self._make_request(f"proposicoes/{proposicao_id}/votacoes")
        return data.get('dados', []) if data else []
    
    def get_votacao_details(self, votacao_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific voting
        """
        return self._make_request(f"votacoes/{votacao_id}")
    
    def get_votacao_votos(self, votacao_id: str) -> List[Dict]:
        """
        Get individual votes for a specific voting
        """
        data = self._make_request(f"votacoes/{votacao_id}/votos")
        return data.get('dados', []) if data else []
    
    def sync_proposicoes_by_year(self, year: int) -> Dict[str, int]:
        """
        Synchronize propositions for a specific year
        """
        data_inicio = f"{year}-01-01"
        data_fim = f"{year}-03-31"
        
        proposicoes_api = self.get_proposicoes_by_date_range(data_inicio, data_fim)
        
        stats = {
            'total_api': len(proposicoes_api),
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        for prop_data in proposicoes_api:
            try:
                with transaction.atomic():
                    self._sync_single_proposicao(prop_data)
                    stats['created'] += 1
            except Exception as e:
                logger.error(f"Error syncing proposition {prop_data.get('id')}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def _sync_single_proposicao(self, prop_data: Dict) -> Proposicao:
        """
        Sync a single proposition from API data
        """
        # Get detailed information
        detailed_data = self.get_proposicao_details(prop_data['id'])
        if detailed_data and 'dados' in detailed_data:
            prop_data.update(detailed_data['dados'])
        
        # Extract fields
        proposicao_data = {
            'id_proposicao': prop_data['id'],
            'titulo': prop_data.get('ementa', '')[:500],  # Limit title length
            'ementa': prop_data.get('ementa', ''),
            'tipo': prop_data.get('siglaTipo', ''),
            'numero': prop_data.get('numero', 0),
            'ano': prop_data.get('ano', 0),
            'autor': self._extract_authors(prop_data.get('autores', [])),
            'estado': prop_data.get('statusProposicao', {}).get('descricaoSituacao', ''),
        }
        
        # Create or update proposition
        proposicao, created = Proposicao.objects.update_or_create(
            id_proposicao=proposicao_data['id_proposicao'],
            defaults=proposicao_data
        )
        
        return proposicao
    
    def _extract_authors(self, autores: List[Dict]) -> str:
        """
        Extract author names from authors list
        """
        if not autores:
            return ''
        
        author_names = []
        for autor in autores[:3]:  # Limit to first 3 authors
            nome = autor.get('nome', '')
            if nome:
                author_names.append(nome)
        
        result = ', '.join(author_names)
        if len(autores) > 3:
            result += f' e mais {len(autores) - 3} autor(es)'
        
        return result[:200]  # Limit length
    
    def sync_votacoes_for_proposicao(self, proposicao: Proposicao) -> int:
        """
        Sync voting data for a specific proposition
        """
        if not proposicao.id_proposicao:
            return 0
        
        votacoes_api = self.get_proposicao_votacoes(proposicao.id_proposicao)
        votacoes_created = 0
        
        for votacao_data in votacoes_api:
            try:
                with transaction.atomic():
                    self._sync_single_votacao(proposicao, votacao_data)
                    votacoes_created += 1
            except Exception as e:
                logger.error(f"Error syncing voting {votacao_data.get('id')}: {e}")
        
        return votacoes_created
    
    def _sync_single_votacao(self, proposicao: Proposicao, votacao_data: Dict) -> VotacaoDisponivel:
        """
        Sync a single voting from API data
        """
        # Get detailed voting information
        detailed_data = self.get_votacao_details(votacao_data['id'])
        if detailed_data and 'dados' in detailed_data:
            votacao_data.update(detailed_data['dados'])
        
        # Parse date
        data_hora_str = votacao_data.get('dataHoraInicio', '')
        data_hora_votacao = None
        if data_hora_str:
            try:
                # API returns dates in ISO format: 2023-12-01T14:30:00
                data_hora_votacao = datetime.fromisoformat(data_hora_str.replace('Z', '+00:00'))
                data_hora_votacao = timezone.make_aware(data_hora_votacao)
            except ValueError:
                logger.warning(f"Could not parse date: {data_hora_str}")
        
        # Extract voting results
        aprovacao = votacao_data.get('aprovacao', 0)
        sim_oficial = votacao_data.get('placarSim', 0)
        nao_oficial = votacao_data.get('placarNao', 0)
        
        votacao_db_data = {
            'proposicao': proposicao,
            'titulo': votacao_data.get('descricao', '')[:200],
            'resumo': votacao_data.get('descricao', ''),
            'data_hora_votacao': data_hora_votacao or timezone.now(),
            'sim_oficial': sim_oficial,
            'nao_oficial': nao_oficial,
            'ativo': False,  # API votings are historical, not active for public voting
        }
        
        # Create or update voting
        votacao, created = VotacaoDisponivel.objects.update_or_create(
            proposicao=proposicao,
            titulo=votacao_db_data['titulo'],
            defaults=votacao_db_data
        )
        
        return votacao
    
    def get_recent_proposicoes(self, days: int = 7) -> List[Dict]:
        """
        Get propositions from the last N days
        """
        data_fim = datetime.now().strftime('%Y-%m-%d')
        data_inicio = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        return self.get_proposicoes_by_date_range(data_inicio, data_fim)
    
    def update_missing_ementas(self) -> int:
        """
        Update propositions that are missing ementa (summary)
        """
        proposicoes_sem_ementa = Proposicao.objects.filter(
            ementa__isnull=True
        ).exclude(id_proposicao__isnull=True)[:50]  # Limit to 50 to avoid API overload
        
        updated_count = 0
        
        for proposicao in proposicoes_sem_ementa:
            try:
                detailed_data = self.get_proposicao_details(proposicao.id_proposicao)
                if detailed_data and 'dados' in detailed_data:
                    ementa = detailed_data['dados'].get('ementa', '')
                    if ementa:
                        proposicao.ementa = ementa
                        proposicao.save(update_fields=['ementa'])
                        updated_count += 1
            except Exception as e:
logger.error(f"Error updating ementa for proposition {proposicao.pk}: {e}")
        
        return updated_count
    
    def sync_proposicoes_by_date_range(self, data_inicio: str, data_fim: str) -> Dict[str, int]:
        """
        Synchronize propositions for a specific date range
        
        Args:
            data_inicio: Start date in YYYY-MM-DD format
            data_fim: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary with sync statistics
        """
        # Validate date format and range
        try:
            inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
            fim = datetime.strptime(data_fim, '%Y-%m-%d')
            
            # Check if the range is not more than 3 months
            max_days = 93  # Approximately 3 months
            if (fim - inicio).days > max_days:
                raise ValueError(f"O período não pode ser superior a {max_days} dias (aproximadamente 3 meses)")
                
            if inicio > fim:
                raise ValueError("A data inicial não pode ser posterior à data final")
                
        except ValueError as e:
            raise ValueError(f"Formato de data inválido ou período inválido: {str(e)}")
        
        proposicoes_api = self.get_proposicoes_by_date_range(data_inicio, data_fim)
        
        stats = {
            'total_api': len(proposicoes_api),
            'created': 0,
            'updated': 0,
            'errors': 0,
            'data_inicio': data_inicio,
            'data_fim': data_fim
        }
        
        for prop_data in proposicoes_api:
            try:
                with transaction.atomic():
                    proposicao, created = self._sync_single_proposicao_with_update_check(prop_data)
                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1
            except Exception as e:
                logger.error(f"Error syncing proposition {prop_data.get('id')}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def _sync_single_proposicao_with_update_check(self, prop_data: Dict) -> tuple[Proposicao, bool]:
        """
        Sync a single proposition from API data with update check
        """
        # Get detailed information
        detailed_data = self.get_proposicao_details(prop_data['id'])
        if detailed_data and 'dados' in detailed_data:
            prop_data.update(detailed_data['dados'])
        
        # Extract fields
        proposicao_data = {
            'id_proposicao': prop_data['id'],
            'titulo': prop_data.get('ementa', '')[:500],  # Limit title length
            'ementa': prop_data.get('ementa', ''),
            'tipo': prop_data.get('siglaTipo', ''),
            'numero': prop_data.get('numero', 0),
            'ano': prop_data.get('ano', 0),
            'autor': self._extract_authors(prop_data.get('autores', [])),
            'estado': prop_data.get('statusProposicao', {}).get('descricaoSituacao', ''),
        }
        
        # Create or update proposition
        proposicao, created = Proposicao.objects.update_or_create(
            id_proposicao=proposicao_data['id_proposicao'],
            defaults=proposicao_data
        )
        
        return proposicao, created


# Global instance
camara_api = CamaraAPIService()