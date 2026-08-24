import os
from slowapi import Limiter
from slowapi.util import get_remote_address

TRUSTED_PROXY = os.getenv("TRUSTED_PROXY", "false").lower() == "true"


# X-Forwarded-For доверенный только при TRUSTED_PROXY=true (прод за nginx),
# и только если nginx ПЕРЕЗАПИСЫВАЕТ заголовок (proxy_set_header
# X-Forwarded-For $remote_addr;), а не добавляет к клиентскому — иначе
# первый IP спуфится и лимиты обходятся.
def _key_func(request):
    if TRUSTED_PROXY:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_key_func, default_limits=["200 per day", "50 per hour"])