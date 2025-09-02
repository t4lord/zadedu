import os, base64
from urllib.parse import urlencode
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import redirect

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


class LoginRequiredMiddleware:
    """
    يفرض تسجيل الدخول على كامل الموقع ما عدا مسارات مستثناة.
    يعتمد على SessionMiddleware و AuthenticationMiddleware، لذا يجب وضعه بعدهما.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # مسارات لا تتطلب تسجيل دخول
        self.exempt_prefixes = (
            '/healthz',        # صحة
            '/static/',        # ملفات ثابتة
            '/admin/login',    # صفحة دخول الإدارة
            '/admin/js/',      # ملفات إدارة
            '/admin/',         # يملك نظامه الخاص
            settings.LOGIN_URL if hasattr(settings, 'LOGIN_URL') else '/accounts/login/',
            '/accounts/logout/',
        )

    def __call__(self, request):
        path = request.path or '/'
        # سمح بالمسارات المعفاة
        if any(path.startswith(p) for p in self.exempt_prefixes):
            return self.get_response(request)

        # إن كان المستخدم مصدقًا، مرر الطلب
        if getattr(request, 'user', None) and request.user.is_authenticated:
            return self.get_response(request)

        # خلاف ذلك، أعد التوجيه لصفحة الدخول مع next
        login_url = getattr(settings, 'LOGIN_URL', '/accounts/login/')
        query = urlencode({'next': request.get_full_path()})
        return redirect(f"{login_url}?{query}")
