# Backup retention policy

The live database is always `storage/forge.db` and is never pruned by a retention command.

- Automated consistent snapshots are compressed under `storage/backups/`; keep the newest **10**.
- Legacy pre-repair snapshots named `storage/forgeos_pre_*.db`; keep the newest **2** on the main volume and archive older copies under `storage/backups/legacy/`.
- Review a dry run first: `cd backend && python -m scripts.backup_retention`.
- Apply it deliberately: `cd backend && python -m scripts.backup_retention --apply`.
- Copy any long-term/legal archive off the main volume before deleting it.
