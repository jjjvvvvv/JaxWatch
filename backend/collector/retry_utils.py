from __future__ import annotations

import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HttpRetrySession:
    """
    Thin wrapper around requests.Session with sensible retry/backoff defaults
    for collection tasks.
    """

    def __init__(self, total: int = 3, backoff_factor: float = 0.5, status_forcelist=None, timeout: float = 30.0):
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(
            total=total,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist or [429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(self, url: str, **kwargs):
        return self.session.get(url, timeout=kwargs.pop("timeout", self.timeout), **kwargs)

    def head(self, url: str, **kwargs):
        return self.session.head(url, timeout=kwargs.pop("timeout", self.timeout), **kwargs)

