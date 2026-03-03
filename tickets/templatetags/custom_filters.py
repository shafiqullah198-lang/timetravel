from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def format_duration(value):
    if not value:
        return ""
    value = value.replace("PT", "")
    hours = ""
    minutes = ""

    if "H" in value:
        hours = value.split("H")[0] + "h "
        value = value.split("H")[1]

    if "M" in value:
        minutes = value.replace("M", "m")

    return hours + minutes
