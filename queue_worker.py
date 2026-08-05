"""A small, rate-limited worker for marketplace jobs."""

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import infrai

DEFAULT_QUEUE = "marketplace-jobs"


class StartRateLimiter:
    """Space job starts evenly across a one-second rate."""

    def __init__(self, per_second: float) -> None:
        if per_second <= 0:
            raise ValueError("per_second must be positive")
        self._interval = 1.0 / per_second
        self._next_start = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_start - now)
            self._next_start = max(now, self._next_start) + self._interval
        if delay:
            time.sleep(delay)


def fulfill_listing(payload: dict) -> None:
    """Replace this domain action with the marketplace fulfillment call."""
    listing = payload.get("listing", "unnamed-listing")
    print(f"fulfilled {listing}")


def _run_one(
    message: dict,
    limiter: StartRateLimiter,
    handler: Callable[[dict], None],
    queue: str,
) -> str:
    limiter.wait()
    handler(message["payload"])
    message_id = message["message_id"]
    infrai.queue.ack(queue=queue, message_id=message_id)
    return message_id


def run_batch(
    concurrency: int = 4,
    per_second: float = 2.0,
    handler: Callable[[dict], None] = fulfill_listing,
    queue: str = DEFAULT_QUEUE,
) -> list[str]:
    """Consume one batch, run jobs concurrently, and acknowledge successes."""
    batch = infrai.queue.consume(
        queue=queue,
        max_messages=concurrency,
        visibility_timeout=60,
    )
    messages = batch.get("items") or []
    limiter = StartRateLimiter(per_second)
    completed: list[str] = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_run_one, message, limiter, handler, queue) for message in messages]
        for future in as_completed(futures):
            completed.append(future.result())
    return completed


def seed_example(queue: str = DEFAULT_QUEUE) -> None:
    infrai.queue.publish(queue=queue, payload={"listing": "handmade-lamp"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one marketplace queue batch")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--per-second", type=float, default=2.0)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    args = parser.parse_args()

    if args.seed:
        seed_example(args.queue)
    completed = run_batch(args.concurrency, args.per_second, queue=args.queue)
    print(f"acknowledged {len(completed)} marketplace job(s)")


if __name__ == "__main__":
    main()
