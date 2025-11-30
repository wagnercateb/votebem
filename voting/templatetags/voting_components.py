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
                else:
                    # Support composite votacao_id in the form "<proposicao_id>-<sufixo>"
                    # Example: "2417025-45" should infer proposicao_id = 2417025
                    vid = request.GET.get('votacao_id')
                    if vid and '-' in vid:
                        leading = vid.split('-', 1)[0]
                        if leading.isdigit():
                            pid = int(leading)
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
                    # Prefer showing the Câmara voting suffix in labels (user-facing)
                    'sufixo': getattr(pv, 'votacao_sufixo', None),
                    'url': f"/voting/votos/oficiais/?votacao_id={pv.id}",
                    'descricao': descricao,
                })

            if pv_items:
                votos_items = pv_items
                main_votos_url = pv_items[0]['url']
                if len(pv_items) == 1:
                    # Show voting suffix when available; fallback to DB id
                    lbl_suffix = pv_items[0].get('sufixo')
                    main_votos_label = f"Votos oficiais {lbl_suffix if lbl_suffix is not None else pv_items[0]['id']}"
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
                    # Try to derive the voting suffix from linked ProposicaoVotacao
                    try:
                        sufixo = getattr(v.proposicao_votacao, 'votacao_sufixo', None)
                    except Exception:
                        sufixo = None
                    if not descricao:
                        descricao = v.titulo
                    vb_items.append({
                        'id': v.id,
                        'sufixo': sufixo,
                        'url': f"/voting/votos/oficiais/?votacao_id={v.id}",
                        'descricao': descricao or '',
                    })
                if vb_items:
                    votos_items = vb_items
                    main_votos_url = vb_items[0]['url']
                    if len(vb_items) == 1:
                        lbl_suffix = vb_items[0].get('sufixo')
                        main_votos_label = f"Votos oficiais {lbl_suffix if lbl_suffix is not None else vb_items[0]['id']}"
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
                            'sufixo': getattr(pv, 'votacao_sufixo', None),
                            'url': f"/voting/votos/oficiais/?votacao_id={pv.id}",
                            'descricao': getattr(pv, 'descricao', '') or ''
                        })
                    if pv_items2:
                        votos_items = pv_items2
                        main_votos_url = pv_items2[0]['url']
                        if len(pv_items2) == 1:
                            lbl_suffix = pv_items2[0].get('sufixo')
                            main_votos_label = f"Votos oficiais {lbl_suffix if lbl_suffix is not None else pv_items2[0]['id']}"
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


# -----------------------------------------------------------------------------
# Reusable ID info component (for inline display of related IDs and links)
# -----------------------------------------------------------------------------
@register.inclusion_tag('components/id_info.html', takes_context=True)
def id_info(
    context: Dict[str, Any],
    votacaovotebem_id: Optional[int] = None,
    proposicaovotacao_id: Optional[int] = None,
    proposicao_id: Optional[int] = None,
    votacao_sufixo: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Renders a compact inline block showing IDs and helpful links related to a
    voting record. Accepts explicit IDs but will infer them from the context if
    not provided, making it usable across different pages and models.

    Inputs (all optional):
    - votacaovotebem_id: ID from table `voting_votacaovotebem`
    - proposicaovotacao_id: ID from table `voting_proposicaovotacao`
    - proposicao_id: Câmara `idProposicao` for external links
    - votacao_sufixo: Câmara voting suffix used in composite voting ids
    """
    try:
        if votacaovotebem_id is None:
            v = context.get('votacao')
            if v and getattr(v, 'id', None):
                votacaovotebem_id = int(v.id)
    except Exception:
        pass

    try:
        if proposicaovotacao_id is None:
            v = context.get('votacao')
            pv = getattr(v, 'proposicao_votacao', None) if v else None
            if pv and getattr(pv, 'id', None):
                proposicaovotacao_id = int(pv.id)
    except Exception:
        pass

    try:
        if proposicao_id is None:
            v = context.get('votacao')
            pv = getattr(v, 'proposicao_votacao', None) if v else None
            prop = getattr(pv, 'proposicao', None) if pv else None
            ip = getattr(prop, 'id_proposicao', None) if prop else None
            if ip:
                proposicao_id = int(ip)
    except Exception:
        pass

    # Fallback inference from request query parameters when creating new records
    # This supports pages like creation forms that only provide IDs via GET,
    # e.g., /gerencial/votacao/create/?proposicao_id=2270325&consulta_id=2270325-92
    try:
        if proposicao_id is None:
            req = context.get('request')
            if req:
                q_prop = req.GET.get('proposicao_id')
                if q_prop and q_prop.isdigit():
                    proposicao_id = int(q_prop)
    except Exception:
        pass

    try:
        if votacao_sufixo is None:
            v = context.get('votacao')
            pv = getattr(v, 'proposicao_votacao', None) if v else None
            s = getattr(pv, 'votacao_sufixo', None) if pv else None
            if s is not None:
                votacao_sufixo = int(s)
    except Exception:
        pass

    # Also try to derive the suffix from composite consulta_id in the URL when present
    try:
        if votacao_sufixo is None:
            req = context.get('request')
            if req:
                comp = req.GET.get('consulta_id')
                if comp and '-' in comp:
                    leading, trailing = comp.split('-', 1)
                    # Only accept when leading matches proposicao_id or is numeric
                    if trailing.isdigit():
                        votacao_sufixo = int(trailing)
                        # If proposicao_id still missing, and leading looks like an id, set it
                        if proposicao_id is None and leading.isdigit():
                            proposicao_id = int(leading)
    except Exception:
        pass

    composite_votacao_id: Optional[str] = None
    try:
        if proposicao_id and votacao_sufixo is not None:
            composite_votacao_id = f"{proposicao_id}-{votacao_sufixo}"
    except Exception:
        composite_votacao_id = None

    proposicao_tramitacao_url: Optional[str] = None
    if proposicao_id:
        proposicao_tramitacao_url = (
            f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={proposicao_id}"
        )

    api_votos_url: Optional[str] = None
    if composite_votacao_id:
        api_votos_url = (
            f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{composite_votacao_id}/votos"
        )

    votacao_detail_url: Optional[str] = None
    if votacaovotebem_id:
        votacao_detail_url = f"http://localhost:8000/voting/votacao/{votacaovotebem_id}/"

    return {
        'votacaovotebem_id': votacaovotebem_id,
        'proposicaovotacao_id': proposicaovotacao_id,
        'proposicao_id': proposicao_id,
        'votacao_sufixo': votacao_sufixo,
        'composite_votacao_id': composite_votacao_id,
        'proposicao_tramitacao_url': proposicao_tramitacao_url,
        'api_votos_url': api_votos_url,
        'votacao_detail_url': votacao_detail_url,
    }
