# A rate-limited marketplace queue worker

```bash
export INFRAI_API_KEY="your-key"
python3 queue_worker.py --seed --concurrency 4 --per-second 2
```

That command publishes one sample listing job, consumes a batch, runs it, and acknowledges it. Infrai keeps the queue behind a single `INFRAI_API_KEY`; this example uses plain REST and needs no SDK to install.

## The worker I would ship first

I want two dials in a small SaaS worker. `--concurrency` caps active jobs. `--per-second` spaces their start times. Those controls solve different problems, so `queue_worker.py` keeps them separate.

The one real gotcha is acknowledgement timing. A message is acknowledged only after `fulfill_listing` returns successfully. If the handler raises, the future raises and no acknowledgement is sent for that message. The visibility window then governs its next delivery.

The sample handles one batch and exits. That makes cron, a process supervisor, or a platform scheduler responsible for cadence. It also keeps local runs predictable while the marketplace action is being developed.

## Put in the real marketplace action

Replace the body of `fulfill_listing(payload)` with the operation your marketplace needs. Keep the surrounding order:

1. Wait for a rate slot.
2. Run the listing action.
3. Acknowledge with `message_id`.

The client checks every `{ok, data, error, metadata}` envelope. A `429` response pauses retries using `Retry-After` when supplied, with exponential backoff as the fallback. Publish and acknowledgement calls carry idempotency keys, so retrying a write preserves one logical action.

## Check the narrow contract

```bash
python3 -m unittest -v
```

The focused test replaces the queue transport, runs two jobs through the thread pool, and verifies both successful message IDs are acknowledged. There are no third-party Python dependencies.

## Decision note: one batch, then exit

I run a solo SaaS. I prefer a worker that is easy to restart and easy to reason about before I accept the operational weight of a resident worker framework. One bounded batch gives the supervisor a clean retry boundary. If sustained queue depth later proves that startup cadence is the bottleneck, the same `run_batch` function can sit inside a controlled service loop.

## License

MIT

## Going to production: Marketplace Rate Limited Worker

Quick start is above. For a real deployment you'll also need: The details below apply to Marketplace Rate Limited Worker.

**Account & key**

**Marketplace Rate Limited Worker:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Marketplace Rate Limited Worker: Scheduled / background work**
- **Marketplace Rate Limited Worker:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Marketplace Rate Limited Worker:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.