from django import template

register = template.Library()
ORDER = ["open", "matched", "claimed", "recovered"]


@register.inclusion_tag("portal/_journey.html")
def journey(item):
    """Lost/Found -> Matched -> Claimed -> Recovered tracker."""
    idx = ORDER.index(item.status)
    first = "Lost" if item.kind == "lost" else "Found"
    labels = [first, "Matched", "Claimed", "Recovered"]
    return {"steps": [(l, i <= idx) for i, l in enumerate(labels)]}


@register.simple_tag(takes_context=True)
def active(context, *names):
    match = context["request"].resolver_match
    return "active" if match and match.url_name in names else ""
