from django import template
from django.utils.timezone import localtime, now

register = template.Library()

@register.simple_tag
def relative_url(value, field_name, urlencode=None):
    url = '?{}={}'.format(field_name, value)
    if urlencode:
        querystring = urlencode.split('&')
        filtered_querystring = filter(lambda p: p.split('=')[0] != field_name, querystring)
        encoded_querystring = '&'.join(filtered_querystring)
        url = '{}&{}'.format(url, encoded_querystring)
    return url

@register.filter
def nombre_completo(usuario):
    """Muestra el nombre completo del usuario con fallback."""
    if hasattr(usuario, 'first_name') and usuario.first_name:
        return f"{usuario.first_name} {usuario.last_name}"
    return usuario.username

@register.filter
def iniciales(nombre):
    """Convierte 'Franco López Pintos' → 'F. L. P.'"""
    if not nombre:
        return ""
    return " ".join([f"{p[0].upper()}." for p in nombre.split() if p])

@register.filter
def fecha_humana(fecha):
    """Formatea la fecha en un estilo legible"""
    if not fecha:
        return "Sin registrar"
    return localtime(fecha).strftime("%d/%m/%Y %H:%M")

# --- TAGS PERSONALIZADOS ---

@register.simple_tag
def saludo_hora():
    """Devuelve un saludo dinámico según la hora"""
    hora = now().hour
    if hora < 12:
        return "¡Buenos días!"
    elif hora < 19:
        return "¡Buenas tardes!"
    return "¡Buenas noches!"