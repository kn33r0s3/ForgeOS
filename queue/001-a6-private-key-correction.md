# 001 — A6 private-key correction scan

- **Finding:** CAPABILITY_QUEUE.md top A6 audit entry (1,045,459 B, 6,388 lines, 18 Nov 16:34): Gitleaks scanned 2,048 commits (103 generic-api-key candidates), TruffleHog 129 unverified records, no private-key rule matched — but the "private-key header 0" claim has NO preserved output file, so it is unproven. The staged order is at /tmp/a6-private-key-correction-order.md.
- **Owner:** Copilot
- **Input:** /tmp/a6-private-key-correction-order.md (scan EVERY blob in history for private-key headers: PKCS#8, PGP, PuTTY, JWK, binary containers, base64-encoded, unreachable objects)
- **Output:** a new top entry in docs/CAPABILITY_QUEUE.md with the real verified private-key count, plus preserved evidence files in /tmp/forgeos-a6-credential-audit-20261118T1014Z/evidence/
- **Verify:** `grep -c` the queue entry for the count; list the evidence dir and confirm the output file exists and is non-empty
- **If blocked:** record exactly which step failed and why in the queue entry; do NOT claim a zero from a failed scan
