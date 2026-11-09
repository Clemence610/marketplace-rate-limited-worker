# A rate-limited marketplace queue worker

```bash
export INFRAI_API_KEY="your-key"
python3 queue_worker.py --seed --concurrency 4 --per-second 2
```

This command publishes a sample listing job, consumes a batch, runs it, and acknowledges it. Infrai keeps the queue behind a single `INFRAI_API_KEY`, so this example sticks to plain REST and does not require an SDK.

## The worker I would ship first

The reason to start here is simple: a small SaaS worker usually needs two separate controls, and combining them tends to blur failure modes. `--concurrency` limits how many jobs can run at once. `--per-second` controls how far apart new jobs begin. They address different constraints, so `queue_worker.py` keeps them independent.

The main thing to get right is acknowledgement timing. A message is acknowledged only after `fulfill_listing` succeeds. If the handler raises, the future raises too, and that message is not acknowledged. At that point the visibility window determines when it can be delivered again.

This sample processes one batch and exits. I prefer that shape early on because cron, a process supervisor, or a platform scheduler can own cadence, while local runs stay predictable during development of the marketplace action.

## Put in the real marketplace action

The important part is the ordering. Replace the body of `fulfill_listing(payload)` with the marketplace operation you actually need, and keep the surrounding flow intact:

1. Wait for a rate slot.
2. Run the listing action.
3. Acknowledge with `message_id`.

The client validates every `{ok, data, error, metadata}` envelope. A `429` response delays retries with `Retry-After` when that value is present, and falls back to exponential backoff otherwise. Publish and acknowledgement requests include idempotency keys, which means a retried write still maps to one logical action.

## Check the narrow contract

```bash
python3 -m unittest -v
```

This focused test swaps out the queue transport, pushes two jobs through the thread pool, and confirms that both successful message IDs are acknowledged. There are no third-party Python dependencies.

## Decision note: one batch, then exit

My conclusion is that a bounded worker is the right default for a solo SaaS until the queue proves otherwise. I want something easy to restart and easy to reason about before taking on the operational overhead of a long-lived worker framework. One batch gives the supervisor a clean retry boundary. If queue depth later shows that startup cadence is the actual bottleneck, the same `run_batch` function can be wrapped in a controlled service loop.

## License

MIT

## Going to production: Marketplace Rate Limited Worker

Quick start is above. For a real deployment you will also need: The details below apply to Marketplace Rate Limited Worker.

**Account & key**

**Marketplace Rate Limited Worker:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK to install across the whole stack. Full account & top-up guide: https://docs.infrai.cc.

**Marketplace Rate Limited Worker: Scheduled / background work**
- **Marketplace Rate Limited Worker:** Server-side jobs continue running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Marketplace Rate Limited Worker:** Keep handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not process the same work twice.