from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class FetchError(Exception):
    pass


class Client:
    def __init__(self):
        self.lock = threading.RLock()
        self.cache = {}
        self.next_request = {}

    def get(self, url, audit, purpose, query=None, attempts=2):
        with self.lock:
            if url in self.cache:
                audit['sources_considered'].append(dict(url=url, purpose=purpose, cached=True))
                return self.cache[url]
        audit['search_attempt_count'] += 1
        audit['search_queries'].append(dict(provider=urlsplit(url).netloc, query=query or url, purpose=purpose))
        audit['sources_considered'].append(dict(url=url, purpose=purpose, cached=False))
        for attempt in range(attempts):
            domain = urlsplit(url).netloc
            with self.lock:
                delay = max(0, self.next_request.get(domain, 0) - time.monotonic())
                self.next_request[domain] = time.monotonic() + delay + (.4 if 'ncbi' in domain else .3)
            if delay:
                time.sleep(delay)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'ClaimLens/0.1 (public claim metadata verification; no bulk CV uploads)', 'Accept': 'application/json, text/html, application/xml;q=0.9, */*;q=0.5'})
                with urllib.request.urlopen(req, timeout=18) as response:
                    if 'application/pdf' in response.headers.get('Content-Type', ''):
                        raise FetchError('PDF requires manual programme inspection')
                    body = response.read(2_500_001)
                    if len(body) > 2_500_000:
                        raise FetchError('source exceeds metadata inspection limit')
                    content = body.decode('utf-8', errors='replace')
                with self.lock:
                    self.cache[url] = content
                return content
            except urllib.error.HTTPError as exc:
                reason = 'HTTP_' + str(exc.code)
                if exc.code in (403, 429, 404, 401):
                    audit['sources_rejected'].append(dict(url=url, rejection_reason=reason))
                    raise FetchError(reason) from None
            except (urllib.error.URLError, TimeoutError, OSError, FetchError) as exc:
                reason = type(exc).__name__
            if attempt + 1 < attempts:
                time.sleep(1 + attempt * 2)
        audit['sources_rejected'].append(dict(url=url, rejection_reason=reason))
        raise FetchError(reason)

    def json(self, url, audit, purpose, query=None):
        try:
            return json.loads(self.get(url, audit, purpose, query))
        except (ValueError, TypeError):
            audit['sources_rejected'].append(dict(url=url, rejection_reason='malformed JSON provider response'))
            raise FetchError('malformed JSON provider response') from None
