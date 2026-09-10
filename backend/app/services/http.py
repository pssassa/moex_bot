from __future__ import annotations

import time
from typing import Any

import httpx

USER_AGENT = "moex-analyst/1.0 (+https://localhost; research)"
ISS_TIMEOUT = httpx.Timeout(90.0, connect=25.0)


class HttpError(RuntimeError):
    pass


def _get(
    url: str,
    params: dict[str, Any] | None,
    headers: dict[str, str],
    *,
    follow_redirects: bool,
    timeout: httpx.Timeout | float,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=timeout,
                headers=headers,
                follow_redirects=follow_redirects,
            )
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001 — ISS иногда отвечает HTML/обрыв
            last_error = exc
            time.sleep(1.2 * (attempt + 1))
    raise HttpError(f"GET {url} failed: {last_error}") from last_error


def get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
    response = _get(
        url,
        params,
        {"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
        timeout=timeout,
    )
    return response.json()


def get_text(url: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> str:
    response = _get(
        url,
        params,
        {"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=timeout,
    )
    return response.text


def get_bytes(url: str, timeout: float = 30.0) -> bytes:
    response = _get(
        url,
        None,
        {"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=timeout,
    )
    return response.content


def iss_get(path: str, params: dict[str, Any] | None = None, accept: str = "application/xml") -> bytes:
    """ISS: сначала HTTP без редиректа на HTTPS, затем HTTPS."""
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    http_url = f"http://iss.moex.com/iss{path}"
    https_url = f"https://iss.moex.com/iss{path}"
    try:
        response = httpx.get(
            http_url,
            params=params,
            timeout=ISS_TIMEOUT,
            headers=headers,
            follow_redirects=False,
        )
        if response.status_code == 200 and response.content:
            return response.content
    except Exception:
        pass
    response = _get(https_url, params, headers, follow_redirects=True, timeout=ISS_TIMEOUT)
    return response.content
