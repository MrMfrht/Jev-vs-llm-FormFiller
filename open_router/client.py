"""Authenticated JSON transport for OpenRouter."""

import json
import os
import logging
from http.client import IncompleteRead
from time import sleep
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

import settings


class OpenRouterError(RuntimeError):
    """The API request failed or the service returned an invalid response."""


def request_decision(payload: dict) -> dict:
    # Jev occasionally never answers a request; a short timeout plus retries keeps the run moving.
    return _post("alpha/decisions", payload, timeout=settings.model_timeout(), attempts=3)


def request_chat(payload: dict, *, timeout: int = 30, attempts: int = 1) -> dict:
    return _post("v1/chat/completions", payload, timeout=timeout, attempts=attempts)


def request_fill_plan(payload: dict) -> dict:
    """A chat request whose answer can be long; wait at least a minute, and retry a hung connection."""
    return request_chat(payload, timeout=max(60, 2 * settings.model_timeout()), attempts=3)


def _post(endpoint: str, payload: dict, *, timeout: int = 30, attempts: int = 1) -> dict:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = os.getenv("OPEN_ROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise OpenRouterError("Set OPEN_ROUTER_API_KEY in .env.")
    request = Request(
        f"https://openrouter.ai/api/{endpoint}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.load(response)
            break
        except HTTPError as exc:
            raise OpenRouterError(f"OpenRouter {endpoint} returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, ConnectionError, IncompleteRead) as exc:
            cause = exc.reason if isinstance(exc, URLError) else exc
            transient = isinstance(cause, (TimeoutError, ConnectionError, IncompleteRead))
            if not transient or attempt == attempts:
                raise OpenRouterError(f"OpenRouter {endpoint} failed on attempt {attempt}: {cause}") from exc
            logging.getLogger(__name__).warning("OpenRouter %s: no answer after %d s (%s). Retrying request (%d/%d).",
                                                endpoint, timeout, cause, attempt + 1, attempts)
            sleep(2 ** (attempt - 1))
        except ValueError as exc:
            raise OpenRouterError("OpenRouter returned invalid JSON.") from exc
    if not isinstance(result, dict):
        raise OpenRouterError("Expected a JSON object from OpenRouter.")
    return result
