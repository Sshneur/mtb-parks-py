from slowapi import Limiter
from slowapi.util import get_remote_address


def _key_func(request):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_key_func, default_limits=["200 per day", "50 per hour"])