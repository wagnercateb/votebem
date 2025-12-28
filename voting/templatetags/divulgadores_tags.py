from django import template
from voting.models import Divulgador

register = template.Library()

@register.simple_tag
def is_divulgador(user):
    if not user or not getattr(user, 'email', None):
        return False
    try:
        Divulgador.objects.get(email__iexact=user.email.strip())
        return True
    except Divulgador.DoesNotExist:
        return False

@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None
