import beeline


class RequestLoggingMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.id:
            beeline.add_trace_field("user.id", request.user.id)
            beeline.add_trace_field("user.email", request.user.email)
            beeline.add_trace_field("user.username", request.user.username)
        return self.get_response(request)
