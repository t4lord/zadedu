import os, base64
from django.http import HttpResponse

class BasicAuthMiddleware:
    """يحمي الموقع كله بـ Basic Auth عند ضبط المتغيرين BASIC_AUTH_USER و BASIC_AUTH_PASS."""
    def __init__(self, get_response):
        self.get_response = get_response
        self.user = os.getenv('BASIC_AUTH_USER')
        self.pw   = os.getenv('BASIC_AUTH_PASS')
        # استثناء مسارات لا تحتاج حماية (صحّة/ملفات ثابتة)
        self.exempt = ('/healthz', '/static/')

    def __call__(self, request):
        if not (self.user and self.pw) or request.path.startswith(self.exempt):
            return self.get_response(request)

        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if auth.startswith('Basic '):
            try:
                decoded = base64.b64decode(auth.split(' ',1)[1]).decode('utf-8')
                u, p = decoded.split(':', 1)
                if u == self.user and p == self.pw:
                    return self.get_response(request)
            except Exception:
                pass

        resp = HttpResponse('Authentication required', status=401)
        resp['WWW-Authenticate'] = 'Basic realm="Restricted"'
        return resp
