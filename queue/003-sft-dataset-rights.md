# 003 — SFT dataset usage rights decision

- **Finding:** CAPABILITY_QUEUE.md SFT entries (smoke test 15:42 + held-out eval 16:34): dataset Saugatkafley/alpaca-nepali-sft, 52,005 rows, has NO explicit licence field. The held-out eval shows the 500-example adapter loses 58 vs 73 to base, so the next step is better data — but NO broader training run is authorised until usage rights are resolved.
- **Owner:** Muse
- **Input:** the dataset card on Hugging Face + the Alpaca source licence (CC BY-NC 4.0) + the local copy at ~/workspace/nepali-data/alpaca-nepali-sft/
- **Output:** a rights memo at ~/workspace/nepali-data/alpaca-nepali-sft-rights.md with a clear YES/NO for (a) local research training, (b) publishing a trained adapter, (c) commercial use
- **Verify:** the memo cites the dataset card + licence text + a dated check; the YES/NO is unambiguous per use
- **If blocked:** if the licence is unclear after checking, write the decision to approvals/ for Niroj and move to task 004; do NOT start a full run on an unclear licence
