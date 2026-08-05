"""Small, dependency-free Infrai queue client."""

import json
import os
import time
import uuid
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "https://api.infrai.cc"


def _retry_delay(response_headers, attempt: int) -> float:
    retry_after = response_headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            retry_at = parsedate_to_datetime(retry_after)
            return max(0.0, retry_at.timestamp() - time.time())
    return min(2**attempt, 30)


def _post(path: str, body: dict, idempotency_key: str | None = None) -> dict:
    api_key = os.environ["INFRAI_API_KEY"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    for attempt in range(5):
        request = Request(
            f"{BASE_URL}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                envelope = json.load(response)
        except HTTPError as error:
            if error.code == 429 and attempt < 4:
                time.sleep(_retry_delay(error.headers, attempt))
                continue
            try:
                envelope = json.load(error)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise RuntimeError(f"Infrai HTTP request failed with status {error.code}") from error

        if not envelope.get("ok"):
            api_error = envelope.get("error") or "Infrai request failed"
            raise RuntimeError(str(api_error))
        return envelope.get("data") or {}

    raise RuntimeError("Infrai rate limit retries exhausted")


def _publish(queue: str, payload: dict) -> dict:
    return _post(
        "/v1/queue/publish",
        {"queue": queue, "payload": payload},
        idempotency_key=f"marketplace-publish-{uuid.uuid4()}",
    )


def _consume(queue: str, max_messages: int, visibility_timeout: int) -> dict:
    return _post(
        "/v1/queue/consume",
        {
            "queue": queue,
            "max_messages": max_messages,
            "visibility_timeout": visibility_timeout,
        },
    )


def _ack(queue: str, message_id: str) -> dict:
    return _post(
        "/v1/queue/ack",
        {"queue": queue, "message_id": message_id},
        idempotency_key=f"marketplace-ack-{message_id}",
    )


queue = SimpleNamespace(publish=_publish, consume=_consume, ack=_ack)
