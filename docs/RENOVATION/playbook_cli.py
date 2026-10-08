#!/usr/bin/env python3
"""
Hami playbook helper. It hands out ONE step at a time, so nobody reads ahead or skips.

  python3 playbook_cli.py next                      show the next step
  python3 playbook_cli.py done N --proof "text"     mark step N done (N must be the next one)
  python3 playbook_cli.py show N                    show step N (only N <= next step)
  python3 playbook_cli.py status                    how far along we are
  python3 playbook_cli.py list                      list the finished steps with their proofs

Keep this file and HAMI_AGENT_PLAYBOOK.txt in the same folder (docs/RENOVATION).
Progress is saved in PROGRESS.md in that folder. That file is the agent's memory.
"""
import re
import sys
import pathlib
import datetime

HERE = pathlib.Path(__file__).resolve().parent
PLAY = HERE / "HAMI_AGENT_PLAYBOOK.txt"
PROG = HERE / "PROGRESS.md"
MARK = re.compile(r"(?m)^=== STEP (\d+) ===[ \t]*$")


def load_steps():
    if not PLAY.exists():
        sys.exit(f"Cannot find {PLAY.name} next to this script. Put both files in the same folder.")
    text = PLAY.read_text(encoding="utf-8")
    marks = list(MARK.finditer(text))
    steps = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        steps[int(m.group(1))] = text[m.start():end].rstrip() + "\n"
    return steps


def last_done():
    if not PROG.exists():
        return 0
    first = PROG.read_text(encoding="utf-8").splitlines()[:1]
    m = re.match(r"LAST DONE STEP:\s*(\d+)", first[0]) if first else None
    return int(m.group(1)) if m else 0


def write_done(n, proof):
    lines = PROG.read_text(encoding="utf-8").splitlines() if PROG.exists() else []
    rest = lines[1:] if lines else []
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rest.append(f"- step {n} done {stamp} | proof: {proof}")
    PROG.write_text(f"LAST DONE STEP: {n}\n" + "\n".join(rest) + "\n", encoding="utf-8")


def phase_of(body):
    m = re.search(r"(?m)^PHASE (\d+) of (\d+): (.+)$", body)
    return m.group(0) if m else None


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    steps = load_steps()
    total = max(steps)
    done = last_done()

    if cmd == "next":
        n = done + 1
        if n > total:
            print(f"All {total} steps are done. Nothing left. Tell the owner.")
            return
        print(steps[n])
    elif cmd == "show":
        if len(args) < 2 or not args[1].isdigit():
            sys.exit("Use: show N")
        n = int(args[1])
        if n not in steps:
            sys.exit(f"There is no step {n}. Steps go from 1 to {total}.")
        if n > done + 1:
            sys.exit(f"No reading ahead. You may only see steps up to {done + 1}.")
        print(steps[n])
    elif cmd == "done":
        if len(args) < 2 or not args[1].isdigit():
            sys.exit('Use: done N --proof "what you saw"')
        n = int(args[1])
        if n != done + 1:
            sys.exit(f"Refused. The next step is {done + 1}, not {n}. One step at a time.")
        if "--proof" not in args:
            sys.exit('Refused. Add --proof "what you saw". A step without proof is not done.')
        proof = " ".join(args[args.index("--proof") + 1:]).strip()
        if len(proof) < 10:
            sys.exit("Refused. The proof is too short. Write what you really saw, in a sentence.")
        write_done(n, proof.replace("\n", " "))
        print(f"Saved. Step {n} of {total} done.")
        if n < total:
            print("Now save with git, then run:  python3 docs/RENOVATION/playbook_cli.py next")
        else:
            print("That was the last step. Tell the owner.")
    elif cmd == "status":
        nxt = done + 1
        print(f"Done {done} of {total} steps.")
        if nxt <= total:
            p = None
            for k in range(nxt, 0, -1):
                p = phase_of(steps[k])
                if p:
                    break
            print(f"Next: step {nxt}.  Current {p or 'phase unknown'}")
        else:
            print("Everything is done.")
    elif cmd == "list":
        if PROG.exists():
            print(PROG.read_text(encoding="utf-8"))
        else:
            print("No steps done yet.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
