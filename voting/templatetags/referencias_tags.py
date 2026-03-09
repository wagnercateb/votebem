from django import template
from voting.models import ProposicaoVotacao

register = template.Library()

@register.inclusion_tag('voting/components/referencias_manager.html')
def render_referencias_manager(proposicao_votacao, show_pv_id=False):
    """
    Renders the Referencias Manager component.
    
    Args:
        proposicao_votacao: A ProposicaoVotacao instance or its ID (int/str).
        show_pv_id: Boolean to toggle display of PV ID in header.
    """
    pv_id = None
    if isinstance(proposicao_votacao, ProposicaoVotacao):
        pv_id = proposicao_votacao.id
    else:
        # Assume it's an ID
        pv_id = proposicao_votacao
    
    return {
        'pv_id': pv_id,
        'show_pv_id': show_pv_id,
    }

@register.filter
def get_referencia_icon(url):
    """
    Returns an icon URL based on the reference URL domain.
    """
    if not url:
        return None
        
    url_str = str(url)
    
    # Estadão
    if url_str.startswith('https://www.estadao.com.br/'):
        return 'https://yt3.ggpht.com/dadwqkT3WM7VFPtTSOfacJmMynJsDTj5EfX6uDL0USiae1ZCzePFidLi4J_tTCQFALPefY11Oxk=s176-c-k-c0x00ffffff-no-rj-mo'
        
    # Folha de S.Paulo
    if url_str.startswith('https://www1.folha.uol.com.br/'):
        return 'https://yt3.googleusercontent.com/hueB58GarYamE3VfoTU_kiHuftYCM_lCZxdkfKbs380f7Obx9HJn8hf0islbiYTj74DFpjONBg=s160-c-k-c0x00ffffff-no-rj'
        
    if url_str.startswith('https://agenciabrasil.ebc.com.br/'):
        return 'https://yt3.ggpht.com/JQI2IGZpd4HizUC8Y0zRjlTpLkPvIBQlj_QWDknsNXM4tlEak1IQJ0Xjn6FC3k2NKxQNy0TCYw=s176-c-k-c0x00ffffff-no-rj-mo'
        
    if url_str.startswith('https://www.camara.leg.br/'):
        return 'https://yt3.googleusercontent.com/mRRHvqtinxHROaGItfNjGkjFjZebfTkg4BhTt4cbY60thJhFGSGuSL1PcNIc7UWU8MqCZdddZA=s160-c-k-c0x00ffffff-no-rj'
        
    if url_str.startswith('http://nexojornal.com.br/'):
        return 'https://yt3.googleusercontent.com/ytc/AIdro_nx_NE8NUVrv60WWnei54c055UZ72eoWeSoZKwGp-gZs8w=s176-c-k-c0x00ffffff-no-rj-mo'
        
    return None

@register.filter
def get_referencia_label(url):
    """
    Returns a short source label based on the reference URL domain.
    """
    if not url:
        return None
        
    url_str = str(url)
    
    # Estadão
    if url_str.startswith('https://www.estadao.com.br/'):
        return 'Estadão'
        
    # Folha de S.Paulo
    if url_str.startswith('https://www1.folha.uol.com.br/'):
        return 'Folha'
        
    # Agência Brasil
    if url_str.startswith('https://agenciabrasil.ebc.com.br/'):
        return 'Agência Brasil'
        
    # Agência Câmara Notícias
    if url_str.startswith('https://www.camara.leg.br/'):
        return 'Agência Câmara Notícias'
        
    # Nexo
    if url_str.startswith('http://nexojornal.com.br/'):
        return 'Nexo'
        
    return None
