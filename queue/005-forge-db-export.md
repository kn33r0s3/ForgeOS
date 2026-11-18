# 005 — forge.db per-table export (Stage 1 seed data)

- **Finding:** forge.db (storage/forge.db, 77,946,880 B) holds the Hami seed data, but a single-file export is blocked on the 50 MB upload limit. The workaround is per-table exports, each under 50 MB.
- **Owner:** Copilot
- **Input:** storage/forge.db (read-only; never write to it)
- **Output:** per-table export files under ~/workspace/nepali-data/seeds/forgeos-export/, each under 50 MB, with a manifest listing table, row count, and file size
- **Verify:** every table in the manifest has a file; row counts match a read-only count query; no file exceeds 50 MB
- **If blocked:** if a single table exceeds 50 MB, split it by row range and record the split in the manifest
