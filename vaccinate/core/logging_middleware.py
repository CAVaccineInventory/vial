import beeline


class RequestLoggingMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.id:
            beeline.add_context(
                {
                    "user.id": request.user.id,
                    "user.email": request.user.email,
                    "user.username": request.user.username,
                }
            )
        return self.get_response(request)
