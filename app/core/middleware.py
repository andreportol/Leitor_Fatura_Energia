import time

from django.conf import settings
from django.contrib.auth import logout
from django.utils.deprecation import MiddlewareMixin


class InactiveLogoutMiddleware(MiddlewareMixin):
    """
    Encerra a sessÇõo do usuÇ­rio apÇüs um perÇ­odo de inatividade.
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        now = time.time()
        last_activity = request.session.get('last_activity') or now
        timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 900)

        if now - last_activity > timeout:
            logout(request)
            request.session.flush()
            return None

        request.session['last_activity'] = now
        return None
