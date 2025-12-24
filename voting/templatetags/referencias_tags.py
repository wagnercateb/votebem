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
