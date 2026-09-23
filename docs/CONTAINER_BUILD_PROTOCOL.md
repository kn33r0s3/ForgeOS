# Container build protocol

## Canonical storage identity

- Host: absolute `<repository>/storage/forge.db`.
- Backend and worker containers: `/app/storage/forge.db`.
- Mapping: the single Compose bind mount `./storage:/app/storage`.
- Relative SQLite URLs are rejected at backend import time.
- Never run host and container schedulers against this file concurrently.

## Backend image

Dependencies are installed into `/app/backend/.deps` with `pip --target`, then exposed through `PYTHONPATH` and `PATH`. No venv or global site-package mutation is required. Optional OpenAI dependencies are installed only with `INSTALL_OPTIONAL_AI=true`.

## Frontend image

The committed `bun.lock` is authoritative. The image uses `bun install --frozen-lockfile`, executes `bun run build`, and starts the Next.js production server rather than a hot-reload development process.

## Baseline verification

```sh
docker compose build
docker compose --profile verify run --rm backend-tests
docker compose build frontend
docker compose up -d
docker compose logs backend | grep "resolved SQLite path"
docker compose exec backend python -m scripts.run_daily_cycle --times 3
tail -c 2000 logs/daily_cycle_log.jsonl
```

The expected startup log path is `/app/storage/forge.db`. On the host, the same file resolves to the repository's absolute `storage/forge.db`.
