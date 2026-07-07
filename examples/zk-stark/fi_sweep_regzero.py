#!/usr/bin/env python3
"""
Fault injection sweep zeroing the twiddle factor register w in fft().

A PC-based register-zero fault targets the lower 32 bits of w (s6/x22)
at the w-initialization point (right after li s6,1).  Since s10 (upper
32 bits) is already set to 0 by the next instruction, this single fault
makes w=0 for the entire group.

With w=0 the butterfly becomes a no-op on the bottom half:
  a[i+j] is unchanged, a[i+j+half] is overwritten with a[i+j].

At p=1.0 the output degenerates to a single public value (1/n mod P),
so the attack is most effective at moderate p where some butterflies
are identity while others mix correctly — creating partial combinations
that leak private transcript values.

Detection: check whether any faulted evaluation equals a private
transcript value (mod P) not present in the honest baseline.
"""

import os
import re
import subprocess

P = (1 << 61) - 1
UINT64_MAX = (1 << 64)

EXAMPLE_DIR   = os.path.dirname(os.path.abspath(__file__))
PROBABILITIES = [round(i * 0.1, 1) for i in range(1, 11)]
RUNS_PER_PROB = 30
TRANSCRIPT_SIZES = [8, 16, 32, 64, 128, 256, 512, 1024]

# Zero s6 (x22) at the instruction after "li s6,1".
# The fault fires before "li s10,0", zeroing s6.  Then li s10,0 sets
# the upper half to 0.  Result: w = (0, 0) = 0 for that group.
PC_W_ZERO = 0x1195c
REG_W_LO  = 22       # s6 = x22

def fibonacci(n):
    seq = [1, 1]
    for i in range(2, n):
        seq.append((seq[-1] + seq[-2]) % UINT64_MAX)
    return seq

def make(*args):
    return subprocess.run(
        ["make", *args],
        cwd=EXAMPLE_DIR,
        capture_output=True,
        text=True,
    )

def build():
    make("clean").check_returncode()
    make("build").check_returncode()

def parse_output(text):
    root        = re.search(r"merkle root: ([0-9a-f]+)", text)
    evals_block = re.search(r"evals:\n(.*?)(?:\n\n|\Z)", text, re.DOTALL)
    evals       = re.findall(r"\[\d+\] = (\d+)", evals_block.group(1)) if evals_block else []
    return (
        root.group(1) if root else None,
        [int(v) for v in evals],
    )

def run_clean(transcript_size):
    r = make("run", f"TRANSCRIPT_SIZE={transcript_size}")
    return parse_output(r.stdout + r.stderr)

def run_fi(prob, transcript_size):
    spec = f"pc:{PC_W_ZERO:#x}:{prob:.1f}:r:{REG_W_LO}:0:FFFFFFFF"
    r = make("run",
             f"FI=--fi-enable --fi-debug --fi-spec={spec}",
             f"TRANSCRIPT_SIZE={transcript_size}")
    text = r.stdout + r.stderr
    root, evals = parse_output(text)
    crashed  = root is None
    triggers = len(re.findall(r"trigger=1", text))
    return root, evals, triggers, crashed

def main():
    print("  building ... ", end="", flush=True)
    build()
    print("done", flush=True)

    for transcript_size in TRANSCRIPT_SIZES:
        transcript_field = {f % P for f in fibonacci(transcript_size)}

        print(f"\n{'='*60}", flush=True)
        print(f"TRANSCRIPT_SIZE={transcript_size}", flush=True)
        print(f"{'='*60}", flush=True)

        _, baseline_evals = run_clean(transcript_size)
        baseline_set = set(baseline_evals)
        detectable   = transcript_field - baseline_set
        print(f"  detectable transcript values: {len(detectable)}\n", flush=True)

        print(f"  {'prob':>6}  {'runs':>5}  {'leaked':>7}  "
              f"{'crashes':>8}  {'avg triggers':>13}", flush=True)
        print(f"  {'-'*50}", flush=True)

        for prob in PROBABILITIES:
            leaked         = 0
            crashes        = 0
            total_triggers = 0

            for _ in range(RUNS_PER_PROB):
                root, evals, triggers, crashed = run_fi(prob, transcript_size)
                total_triggers += triggers

                if crashed:
                    crashes += 1
                else:
                    if detectable & set(evals):
                        leaked += 1

            avg_triggers = total_triggers / RUNS_PER_PROB
            print(f"  {prob:>6.1f}  {RUNS_PER_PROB:>5}  {leaked:>7}  "
                  f"{crashes:>8}  {avg_triggers:>13.1f}", flush=True)

if __name__ == "__main__":
    main()
