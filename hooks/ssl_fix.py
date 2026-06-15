"""
ssl_fix.py - MkDocs hook to work around corrupt Windows certificate store entries.

On some Windows machines, the system ROOT certificate store contains one or more
certificates with corrupt ASN.1 data. Python's ssl module calls
``ssl.create_default_context()`` which internally calls
``load_default_certs()`` → ``_load_windows_store_certs()`` → crashes with
``ssl.SSLError: [ASN1: NOT_ENOUGH_DATA]``.

This hook patches ``ssl.create_default_context`` to skip the Windows store
load. MkDocs only needs SSL for the live-reload server, which is local
(127.0.0.1) and does not require certificate validation.

Loaded via mkdocs.yml:
    hooks:
      - docs/hooks/ssl_fix.py
"""

import ssl
import functools

_original_create_default_context = ssl.create_default_context


@functools.wraps(_original_create_default_context)
def _patched_create_default_context(purpose=ssl.Purpose.SERVER_AUTH, *args, **kwargs):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


ssl.create_default_context = _patched_create_default_context
