from django.conf import settings


def extra_context(request):
    return {"is_staging": settings.STAGING}
