"""Small synchronous API over cancellable HTTP, with one absolute time budget.

The budget includes DNS, connection/TLS, request writes, response headers and
body reads. No HTTP task is delegated to a background thread. Platform DNS is
resolved in a private, bounded subprocess because asyncio's default executor
can otherwise wait for uncancellable getaddrinfo() after a request timeout.
That process receives only a public hostname/port, never headers or payloads;
timeouts kill and reap it before this function returns.

This module has no Django dependency and can also be used by the supervisor.
"""
import asyncio
from dataclasses import dataclass
import ipaddress
import json as json_module
import math
import os
import ssl
import subprocess
import sys
import time

import certifi
import httpcore
import httpx


class RequestError(Exception):
    def __init__(self):
        super().__init__('The bounded HTTP request failed.')


class DeadlineExceeded(RequestError):
    pass


class ResponseTooLarge(RequestError):
    pass


@dataclass(frozen=True)
class Response:
    status_code: int
    body: bytes


_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
_DNS_CODE = '''import json,socket,sys
host,port=json.loads(sys.stdin.read(4096))
addresses=[]
for result in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM):
 address=result[4][0]
 if address not in addresses: addresses.append(address)
 if len(addresses)>=16: break
sys.stdout.write(json.dumps(addresses))
'''


def _remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise DeadlineExceeded()
    return value


def _resolve_ips(host, port, deadline):
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    # No inherited Django/Microsoft secrets, proxy variables, PYTHONPATH or
    # credential-bearing command arguments enter this resolver process.
    environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    try:
        completed = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', _DNS_CODE],
            input=json_module.dumps([host, port]).encode('ascii'), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=environment, timeout=_remaining(deadline),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0,
            check=False)
        if completed.returncode or len(completed.stdout) > 4096:
            raise RequestError()
        values = json_module.loads(completed.stdout)
        if not isinstance(values, list) or not 1 <= len(values) <= 16:
            raise RequestError()
        result = [str(ipaddress.ip_address(value)) for value in values]
        _remaining(deadline)
        return result
    except subprocess.TimeoutExpired:
        # subprocess.run kills the child and waits for it before re-raising.
        raise DeadlineExceeded() from None
    except (OSError, ValueError, TypeError, UnicodeError):
        raise RequestError() from None


class _ResolvedBackend(httpcore.AnyIOBackend):
    def __init__(self, host, addresses):
        self.host = host
        self.addresses = addresses

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != self.host or local_address is not None:
            raise httpcore.ConnectError('Unexpected connection target.')
        for address in self.addresses:
            try:
                # Numeric addresses prevent anyio from invoking its DNS thread
                # pool. HTTP Host and TLS SNI remain the original URL hostname.
                return await super().connect_tcp(address, port, timeout=timeout,
                    local_address=None, socket_options=socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout):
                continue
        raise httpcore.ConnectError('The approved host is unavailable.')


async def _exchange(prepared, addresses, *, deadline, timeout, max_bytes, read_body):
    try:
        async with asyncio.timeout(_remaining(deadline)):
            limits = {'connect': timeout[0], 'read': timeout[1],
                      'write': timeout[1], 'pool': timeout[0]}
            url = httpcore.URL(scheme=prepared.url.raw_scheme, host=prepared.url.raw_host,
                port=prepared.url.port, target=prepared.url.raw_path)
            outbound = httpcore.Request(method=prepared.method, url=url,
                headers=prepared.headers.raw, content=prepared.content,
                extensions={'timeout': limits})
            async with httpcore.AsyncConnectionPool(ssl_context=_SSL_CONTEXT,
                    max_connections=1, max_keepalive_connections=0, retries=0,
                    network_backend=_ResolvedBackend(prepared.url.host, addresses)) as pool:
                response = await pool.handle_async_request(outbound)
                try:
                    body = bytearray()
                    if read_body:
                        async for chunk in response.aiter_stream():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                raise ResponseTooLarge()
                    return Response(response.status, bytes(body))
                finally:
                    await response.aclose()
    except (TimeoutError, httpcore.TimeoutException):
        raise DeadlineExceeded() from None
    except (httpcore.NetworkError, httpcore.ProtocolError, httpcore.ConnectionNotAvailable):
        raise RequestError() from None


def request(method, url, *, total_timeout, timeout=(5, 15), max_bytes,
            headers=None, data=None, json=None, read_body=True):
    """Return a bounded response; never follow redirects or use environment proxies.

    Intended for synchronous workers/supervisors. Callers already running an
    asyncio loop fail explicitly rather than creating a hidden worker thread.
    Responses are raw identity-encoded bytes; the helper does not decompress
    uploaded/provider content or turn oversized responses into partial success.
    """
    try:
        if (type(total_timeout) not in (int, float) or not math.isfinite(total_timeout)
                or not 0 < total_timeout <= 120 or type(max_bytes) is not int
                or not 0 <= max_bytes <= 1024 * 1024 or len(timeout) != 2
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       or not 0 < value <= 120 for value in timeout)):
            raise ValueError
        deadline = time.monotonic() + total_timeout
        prepared = httpx.Request(method, url, headers=headers, data=data, json=json)
        if (prepared.url.scheme not in ('http', 'https') or not prepared.url.host
                or prepared.url.userinfo or len(prepared.content) > 128 * 1024):
            raise ValueError
        prepared.headers['Accept-Encoding'] = 'identity'
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RequestError()
        addresses = _resolve_ips(prepared.url.host, prepared.url.port or
            (443 if prepared.url.scheme == 'https' else 80), deadline)
        # Numeric-only network backend never uses the default DNS executor, so
        # asyncio.run cleanup cannot wait on an uncancellable resolver thread.
        return asyncio.run(_exchange(prepared, addresses, deadline=deadline,
            timeout=timeout, max_bytes=max_bytes, read_body=read_body))
    except (ValueError, TypeError, UnicodeError, httpx.HTTPError):
        raise RequestError() from None
