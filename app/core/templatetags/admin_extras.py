from django import template

from app.core.models import Cliente

register = template.Library()


@register.simple_tag
def vip_pending_count():
    return Cliente.objects.filter(vip_request_pending=True).count()


@register.simple_tag
def vip_pending_clients(limit=5):
    qs = (
        Cliente.objects.filter(vip_request_pending=True)
        .order_by('nome')
        .values_list('nome', flat=True)
    )
    limit = int(limit or 5)
    return list(qs[:limit])
