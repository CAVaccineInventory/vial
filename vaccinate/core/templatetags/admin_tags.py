from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def get_claimed_by_user_style(context):
    original = context["original"]
    request = context["request"]

    if original.claimed_by == request.user:
        return "current-user"
    else:
        return "user"


@register.simple_tag(takes_context=True)
def num_claimed_reports(context):
    if context["name"] == "location":
        return context["your_pending_claimed_locations"]
    else:
        return context["your_pending_claimed_reports"]
