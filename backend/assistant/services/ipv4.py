"""Force IPv4 for specific outbound HTTP clients.

On networks where the IPv6 route to a host is blackholed (packets dropped
rather than cleanly refused), the OS default connect order tries IPv6 first and
stalls for the full socket timeout before falling back to IPv4 — on every fresh
connection. GitHub (content_loader's `requests` calls) and the Google/Gemini
APIs (the google-genai SDK's `httpx` calls) both publish IPv6 records, so both
are affected.

Rather than patch the process-global `socket.getaddrinfo` — which would also
silently reshape DNS for Postgres, Redis, and every other outbound connection —
we force IPv4 only on the two clients that need it, via the same underlying
trick in both:

    Bind the outgoing socket to the IPv4 wildcard source address ("0.0.0.0").

`socket.create_connection` walks the resolved addresses and, for each, opens a
socket of that address family and binds the source. Binding an IPv4 source to
an IPv6 (AF_INET6) socket fails, so IPv6 candidates are skipped and only the
IPv4 address is used. No monkeypatching, no global state.
"""

from __future__ import annotations

from functools import lru_cache

_IPV4_WILDCARD = "0.0.0.0"


# ── requests (GitHub content fetches) ─────────────────────────────────────────

@lru_cache(maxsize=1)
def requests_session():
    """A `requests.Session` whose HTTPS/HTTP connections are pinned to IPv4."""
    import requests
    from requests.adapters import HTTPAdapter

    class _IPv4Adapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs["source_address"] = (_IPV4_WILDCARD, 0)
            super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, *args, **kwargs):
            kwargs["source_address"] = (_IPV4_WILDCARD, 0)
            return super().proxy_manager_for(*args, **kwargs)

    session = requests.Session()
    adapter = _IPv4Adapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ── httpx (Gemini SDK) ────────────────────────────────────────────────────────

def httpx_client_args() -> dict:
    """Kwargs for google-genai's `HttpOptions.client_args` that pin httpx to IPv4.

    Passed to the underlying `httpx.Client`, whose transport binds outgoing
    connections to the IPv4 wildcard source address.
    """
    import httpx

    return {"transport": httpx.HTTPTransport(local_address=_IPV4_WILDCARD)}


def httpx_async_client_args() -> dict:
    """Async counterpart to `httpx_client_args` for `HttpOptions.async_client_args`."""
    import httpx

    return {"transport": httpx.AsyncHTTPTransport(local_address=_IPV4_WILDCARD)}
