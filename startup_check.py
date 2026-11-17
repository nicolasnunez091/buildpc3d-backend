"""Comprobación temporal de arranque; sin endpoints y sin datos privados en logs."""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from production import _RESERVE_SCRIPT, _RELEASE_SCRIPT


def _report(label, ok):
    # Etiquetas constantes, nunca imprimir excepciones, argumentos ni URLs.
    print("UPSTASH_CHECK " + label + (" OK" if ok else " FALLO"), flush=True)


def check_redis(client):
    """Ensayo Lua aislado. Las claves restantes caducan, sin borrar datos."""
    old_prefix = "bpc:public:day:"
    old_hour_ttl = "redis.call('EXPIRE', KEYS[1], 3600)"
    old_daily_ttl = "86400 - (now % 86400)"
    if not (_RESERVE_SCRIPT.count(old_prefix) == 1
            and _RESERVE_SCRIPT.count(old_hour_ttl) == 1
            and _RESERVE_SCRIPT.count(old_daily_ttl) == 1):
        raise ValueError("unsupported script")
    prefix = "bpc:diagnostico:" + secrets.token_hex(16) + ":"
    script = (_RESERVE_SCRIPT.replace(old_prefix, prefix + "day:")
              .replace(old_hour_ttl, "redis.call('EXPIRE', KEYS[1], 300)")
              .replace(old_daily_ttl, "math.min(300, 86400 - (now % 86400))"))
    active = prefix + "active"
    if client.ping() is not True:
        raise ValueError("ping")
    _report("TLS_PING", True)

    def reserve(i):
        return client.eval(script, 2, prefix + "hour", active,
                           10, 100, 2, 120, "lease-" + str(i))

    # Las dos reservas admitidas se mantienen hasta finalizar las 8 llamadas.
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(reserve, range(8)))
    if results.count(1) != 2 or results.count(0) != 6:
        raise ValueError("concurrency")
    for index, result in enumerate(results):
        if result == 1:
            client.eval(_RELEASE_SCRIPT, 1, active, "lease-" + str(index))
    # Comprobar TTL de una clave escrita por el script (ningún valor privado).
    ttl = client.ttl(prefix + "hour")
    if not 0 < ttl <= 300:
        raise ValueError("ttl")
    _report("LUA_CONCURRENCIA_TTL", True)


def run():
    """No muestra excepciones ni siquiera si la URL contiene credenciales."""
    try:
        url = os.environ.get("REDIS_URL", "").strip()
        parsed = urlsplit(url)
        if parsed.scheme != "rediss" or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError("url")
        client = Redis.from_url(
            url, ssl_cert_reqs="required", ssl_check_hostname=True,
            socket_connect_timeout=3, socket_timeout=3,
            retry=Retry(NoBackoff(), 0), retry_on_timeout=False,
        )
        try:
            check_redis(client)
        finally:
            client.close()
        return True
    except Exception:
        _report("DIAGNOSTICO", False)
        return False
