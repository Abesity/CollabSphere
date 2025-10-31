from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """
    Multiply numeric values in templates.
    Example: {{ 5|mul:2 }} → 10
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

