# ForgeOS hosting and scheduler decision

**Decision (2026-09-29):** Do not buy hosting or a scheduler before first real
customer revenue. Do not use the current Vercel Hobby deployment for commercial
pilot operations: the account is on Hobby, whose official terms restrict it to
personal, non-commercial use. Keep Forge Bot disabled until there is owner
discovery, explicit contact authorization, and a commercially permitted,
reliable task runner. The existing production deployment is useful for
technical verification, not evidence that commercial hosting is permitted.

## Verified current infrastructure

- Production health reported PostgreSQL configured and reachable through
  `DATABASE_URL`; the deployed app is not using SQLite. The underlying
  PostgreSQL vendor was not verified from the health contract and is not
  guessed here.
- Vercel team plan observed: **Hobby**. `vercel.json` configures only
  `/api/scheduled/cycle` at `0 0 * * *`. Vercel documents Hobby cron as once
  daily with per-hour precision (up to ±59 minutes). This cannot run timely
  follow-ups or reminders.
- `backend/worker.py` is a separate process that polls `WorkerTask` on a
  30-minute default interval and dispatches integrations. Repository/runtime
  inspection did not find it wired as an always-running production process.
  Demand intake also uses request-scoped FastAPI background work; that is not a
  durable, independent scheduler.
- The existing `WorkerTask` supports due times, idempotency, claim/processing,
  and retry. Reuse it; do not add another queue/state system. Production must
  still run a reliable poller to act on due tasks.

## Cost and permitted choices

| Option | Direct cost / current terms | Fit and limitation |
|---|---|---|
| Existing owner-controlled computer, if already available | No new hosting subscription; electricity/network and uptime are not zero-cost guarantees. Use only existing hardware and an authorized connection. | Can run the existing container/API plus native worker without a new vendor. Availability, backups, network exposure, and recovery need proof before a real pilot. |
| GitHub Actions hosted runner | Standard hosted-runner usage is free for public repositories under GitHub's published billing terms. | Commercially usable for CI, but it is not a host. Scheduled workflow timing is not a durable sub-daily production scheduler; do not build the Bot around it. |
| Google Cloud Run free usage tier | Monthly request-based allowances include 2 million requests, 180,000 vCPU-seconds, and 360,000 GiB-seconds in the listed model; a billing account/payment method is required and overages can bill. | Runs containerized FastAPI and can scale down. It is not a free always-on worker; a scheduled invocation and the separate PostgreSQL bill remain additional. Treat compute as $0 only after an account-specific cost/terms check, never as guaranteed free. |

No managed, fully $0 production option with a dependable sub-daily worker has
been verified. Free allowances are usage-limited, may change, and are not a
promise of availability or a $0 invoice. Check the provider terms, region,
account billing, data location, subprocess support, and database charges
before adoption. Cloudflare Workers has a free tier, but it is not a direct
host for this Python/FastAPI + PostgreSQL application and its service-specific
data handling has not been cleared for this use.

The current **Vercel Hobby** plan is $0 but is restricted to personal,
non-commercial use; its cron is once daily with up to ±59-minute precision.
It is recorded as current infrastructure, not as a commercially eligible
hosting choice.

## Lowest-cost managed fallback after first payment

The lowest listed scheduler price verified is **Google Cloud Scheduler at
$0.10 per job per 31 days** (charged per job, not per invocation). After first
payment, one bounded scheduled request could claim due `WorkerTask`s from a
Cloud Run service; the service's usage may fit its free allowance, but exceeding
it bills and PostgreSQL remains a separate cost. This is a candidate, not a
deployment recommendation: validate account terms, region, end-to-end recovery,
and database costs first.

If retaining the current Vercel deployment is worth the higher base plan cost,
**Vercel Pro is $20/month** and documents cron down to once per minute. That
enables frequent HTTP-triggered task claims, not an always-running worker; the
endpoint must remain bounded and idempotent. Budget separately for PostgreSQL,
usage beyond included credits, backups, and any communication provider. Do not
upgrade or purchase before first customer payment unless a documented legal,
security, payment, or critical-execution need is approved. Recheck terms and
price at the purchase date.

## Sources

- [Vercel Hobby plan and commercial-use restriction](https://vercel.com/docs/plans/hobby)
- [Vercel Cron usage, schedule precision, and plan intervals](https://vercel.com/docs/cron-jobs/usage-and-pricing)
- [Vercel Pro plan](https://vercel.com/docs/plans/pro-plan) and
  [pricing](https://vercel.com/pricing)
- [Google Cloud Run pricing](https://cloud.google.com/run/pricing) and
  [FastAPI deployment quickstart](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service)
- [Google Cloud Scheduler pricing](https://cloud.google.com/scheduler/pricing)
- [Google Cloud Terms](https://cloud.google.com/terms/)
- [GitHub Actions billing and usage](https://docs.github.com/en/actions/concepts/billing-and-usage)
