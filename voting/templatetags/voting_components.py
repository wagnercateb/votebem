from typing import Any, Dict, List, Optional

from django import template
from django.utils.safestring import mark_safe

from voting.models import VotacaoVoteBem, ProposicaoVotacao, CongressmanVote
from django.db.models import Q

register = template.Library()


def _extract_proposicao_id_from_context(context: Dict[str, Any]) -> Optional[int]:
    """
    Try to infer proposicao_id from common context variables.
    Supports contexts that include:
    - proposicao (with id_proposicao)
    - votacao (VotacaoVoteBem -> proposicao_votacao -> proposicao.id_proposicao)
    - votacoes (list/queryset of VotacaoVoteBem)
    - proposicao_votacao or pv (with proposicao_id or proposicao.id_proposicao)
    """
    try:
        proposicao = context.get('proposicao')
        if proposicao and hasattr(proposicao, 'id_proposicao') and proposicao.id_proposicao:
            return int(proposicao.id_proposicao)
    except Exception:
        pass

    try:
        votacao = context.get('votacao')
        if votacao and getattr(votacao, 'proposicao_votacao', None):
            prop = getattr(votacao.proposicao_votacao, 'proposicao', None)
            if prop and getattr(prop, 'id_proposicao', None):
                return int(prop.id_proposicao)
    except Exception:
        pass

    try:
        votacoes = context.get('votacoes')
        if votacoes:
            first = None
            try:
                first = votacoes[0]
            except Exception:
                # If it's a queryset, use first()
                try:
                    first = votacoes.first()
                except Exception:
                    first = None
            if first and getattr(first, 'proposicao_votacao', None):
                prop = getattr(first.proposicao_votacao, 'proposicao', None)
                if prop and getattr(prop, 'id_proposicao', None):
                    return int(prop.id_proposicao)
    except Exception:
        pass

    for key in ('proposicao_votacao', 'pv'):
        try:
            pv = context.get(key)
            if pv:
                # Prefer explicit field
                if hasattr(pv, 'proposicao_id') and pv.proposicao_id:
                    return int(pv.proposicao_id)
                # Fallback via relation
                prop = getattr(pv, 'proposicao', None)
                if prop and getattr(prop, 'id_proposicao', None):
                    return int(prop.id_proposicao)
        except Exception:
            pass

    return None


@register.inclusion_tag('components/proposicao_action_bar.html', takes_context=True)
def proposicao_action_bar(context: Dict[str, Any], proposicao_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Render a reusable action bar for a proposição, containing three buttons:
    - "Obter votações da proposição" -> /gerencial/?proposicao_id=<id>
    - "Votos oficiais" (split dropdown listing each VotacaoVoteBem id)
      -> /voting/votos/oficiais/?votacao_id=<votacao_id>, tooltip uses descrição
        from the linked ProposicaoVotacao when available.
    - "Editar votações VoteBem" -> /gerencial/votacao/<id>/edit/

    If no proposicao_id is provided, the tag tries to infer it from the context.
    """
    # Detect proposicao_id if not explicitly provided
    pid = proposicao_id or _extract_proposicao_id_from_context(context)

    # Fallback: read from request querystring if available
    if not pid:
        try:
            request = context.get('request')
            if request:
                qid = request.GET.get('proposicao_id')
                if qid:
                    pid = int(qid)
        except Exception:
            pass

    # Build URLs or leave None when unavailable (for disabled state in UI)
    obter_votacoes_url = f"/gerencial/?proposicao_id={pid}" if pid else None
    editar_votacoes_url = f"/gerencial/votacao/{pid}/edit/" if pid else None

    # Collect available VotacaoVoteBem entries for this proposição
    votos_items: List[Dict[str, Any]] = []
    main_votos_url: Optional[str] = None
    main_votos_label: str = "Votos oficiais"

    if pid:
        try:
            # Prefer listing ProposicaoVotacao IDs that have official counts OR congressman votes
            pv_qs = (
                ProposicaoVotacao.objects
                .filter(
                    # Either official counts are non-zero OR there exist CongressmanVote rows
                    Q(sim_oficial__gt=0) | Q(nao_oficial__gt=0) | Q(congressmanvote__isnull=False),
                    proposicao_id=pid,
                )
                .select_related('proposicao')
                .order_by('prioridade', 'id')
                .distinct()
            )

            pv_items: List[Dict[str, Any]] = []
            for pv in pv_qs:
                descricao = getattr(pv, 'descricao', '') or ''
                pv_items.append({
                    'id': pv.id,
                    'url': f"/voting/votos/oficiais/?votacao_id={pv.id}",
                    'descricao': descricao,
                })

            if pv_items:
                votos_items = pv_items
                main_votos_url = pv_items[0]['url']
                if len(pv_items) == 1:
                    main_votos_label = f"Votos oficiais {pv_items[0]['id']}"
            else:
                # Fallback to VotacaoVoteBem entries linked to a ProposicaoVotacao of this proposição
                vb_qs = (
                    VotacaoVoteBem.objects
                    .filter(proposicao_votacao__proposicao_id=pid)
                    .select_related('proposicao_votacao')
                    .order_by('id')
                )
                vb_items: List[Dict[str, Any]] = []
                for v in vb_qs:
                    descricao = None
                    try:
                        descricao = getattr(v.proposicao_votacao, 'descricao', None)
                    except Exception:
                        descricao = None
                    if not descricao:
                        descricao = v.titulo
                    vb_items.append({
                        'id': v.id,
                        'url': f"/voting/votos/oficiais/?votacao_id={v.id}",
                        'descricao': descricao or '',
                    })
                if vb_items:
                    votos_items = vb_items
                    main_votos_url = vb_items[0]['url']
                    if len(vb_items) == 1:
                        main_votos_label = f"Votos oficiais {vb_items[0]['id']}"
                else:
                    # Last-resort: list all PV for the proposição so the button stays usable
                    pv_all = (
                        ProposicaoVotacao.objects
                        .filter(proposicao_id=pid)
                        .order_by('prioridade', 'id')
                    )
                    pv_items2: List[Dict[str, Any]] = []
                    for pv in pv_all:
                        pv_items2.append({
                            'id': pv.id,
                            'url': f"/voting/votos/oficiais/?votacao_id={pv.id}",
                            'descricao': getattr(pv, 'descricao', '') or ''
                        })
                    if pv_items2:
                        votos_items = pv_items2
                        main_votos_url = pv_items2[0]['url']
                        if len(pv_items2) == 1:
                            main_votos_label = f"Votos oficiais {pv_items2[0]['id']}"
        except Exception:
            # In case of query issues, keep empty items to render disabled state
            votos_items = []
            main_votos_url = None

    return {
        'proposicao_id': pid,
        'obter_votacoes_url': obter_votacoes_url,
        'editar_votacoes_url': editar_votacoes_url,
        'votos_items': votos_items,
        'main_votos_url': main_votos_url,
        'main_votos_label': main_votos_label,
    }


# -----------------------------------------------------------------------------
# Sorting filter for party groups used in the ranking template
# -----------------------------------------------------------------------------
@register.filter(name="sort_groups_by_size_and_name_desc")
def sort_groups_by_size_and_name_desc(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort party regroup entries primarily by group size (descending),
    and secondarily by party name (descending alphabetical order).

    Expected input (from Django `{% regroup %}`): a list of dicts, each with:
      - `grouper`: the party name (string)
      - `list`:   the list of items for that party within the current score

    This function is defensive: if the input is not in the expected format,
    it will try to coerce missing fields and fail gracefully.
    """
    try:
        # Normalize to a list to prevent errors if `groups` is None or another iterable
        normalized: List[Dict[str, Any]] = []
        for g in groups or []:
            # Ensure dict-like access
            if isinstance(g, dict):
                party_name = str(g.get('grouper', '') or '')
                items = g.get('list') or []
            else:
                # Fallback: attempt attribute access if not a dict
                party_name = str(getattr(g, 'grouper', '') or '')
                items = getattr(g, 'list', []) or []

            # Compute size safely
            try:
                size = len(items)
            except Exception:
                size = 0

            normalized.append({'grouper': party_name, 'list': items, '_size': size})

        # Sort by size desc, then name desc
        normalized.sort(key=lambda x: (x['_size'], x['grouper']), reverse=True)

        # Remove helper field before returning, to keep the original structure
        for n in normalized:
            if '_size' in n:
                del n['_size']

        return normalized
    except Exception:
        # On any unexpected error, return the groups unchanged
        return groups or []