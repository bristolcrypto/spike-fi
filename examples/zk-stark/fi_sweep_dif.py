#!/usr/bin/env python3
"""
Fault injection sweep on the Gentleman-Sande (DIF) NTT.

In DIF the stages run from largest (len=n) to smallest (len=2), with
bit-reversal at the output.  The first stage has n/2 j-iterations in a
single group — skipping the back-edge at j=0 leaves n-2 positions
untouched at the most mixing stage.

The j=0-only DIF inverse recovers raw inputs from the faulted output.
Each position is checked against the public Fibonacci constraints.
"""

import argparse
import os
import re
import random
import subprocess
from math import log2

P = (1 << 61) - 1
UINT64_MAX = (1 << 64)

EXAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))

# j-loop back-edge PC for DIF fft()
BACK_EDGE_PC = 0x11bae

def _bit_reverse(a):
    n = len(a); out = list(a); j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit; bit >>= 1
        j ^= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    return out

def _inv_fft_j0_dif(a):
    """
    Inverse of the j=0-only Gentleman-Sande (DIF) FFT.

    Forward DIF j=0: stages len=n..2 with butterfly (u+v, u-v),
    then bit-reverse output.

    Inverse: undo bit-reverse, then undo stages len=2..n.
    """
    n = len(a)
    a = _bit_reverse(list(a))
    inv2 = pow(2, P - 2, P)
    length = 2
    while length <= n:
        half = length // 2
        for i in range(0, n, length):
            s, d = a[i], a[i + half]
            a[i]        = (s + d) * inv2 % P
            a[i + half] = (s + P - d) * inv2 % P
        length *= 2
    return a

def _fft_j0_dif(a):
    """Forward j=0-only DIF FFT."""
    n = len(a); a = list(a)
    length = n
    while length >= 2:
        half = length // 2
        for i in range(0, n, length):
            u, v = a[i], a[i + half]
            a[i]        = (u + v) % P
            a[i + half] = (u + P - v) % P
        length //= 2
    return _bit_reverse(a)

def _expected_faulted_evals(transcript_field, transcript_size):
    n     = transcript_size
    inv_n = pow(n, P - 2, P)
    coeffs = _fft_j0_dif(list(transcript_field))
    coeffs = [(x * inv_n) % P for x in coeffs]
    return _fft_j0_dif(coeffs + [0] * n)

def try_extract(faulted_evals, transcript_size, expected_faulted, baseline_set, num_queries):
    ext = 2 * transcript_size
    nq  = min(num_queries, ext)
    queries = random.sample(range(ext), nq)
    for q in queries:
        if faulted_evals[q] == expected_faulted[q] and faulted_evals[q] not in baseline_set:
            return True
    return False

# ── Sweep infrastructure ─────────────────────────────────────────────────────

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
    make("build", "TEST_SRC=test_dif.c").check_returncode()

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
    spec = f"pc:{BACK_EDGE_PC:#x}:{prob:.1f}:s"
    r    = make("run", f"FI=--fi-enable --fi-debug --fi-spec={spec}",
                f"TRANSCRIPT_SIZE={transcript_size}")
    text = r.stdout + r.stderr
    root, evals = parse_output(text)
    crashed  = root is None
    triggers = len(re.findall(r"trigger=1", text))
    return root, evals, triggers, crashed

def parse_args():
    ap = argparse.ArgumentParser(description="DIF loop-skip FI sweep")
    ap.add_argument("-n", "--sizes", type=int, nargs="+",
                    default=[8, 16, 32, 64, 128, 256, 512, 1024])
    ap.add_argument("-p", "--probs", type=float, nargs="+",
                    default=[round(i * 0.1, 1) for i in range(1, 11)])
    ap.add_argument("-q", "--queries", type=int, nargs="+", default=[64])
    ap.add_argument("-r", "--runs", type=int, default=30)
    return ap.parse_args()

def main():
    args = parse_args()

    print("  building ... ", end="", flush=True)
    build()
    print("done", flush=True)

    for transcript_size in args.sizes:
        fib = fibonacci(transcript_size)
        transcript_field = [f % P for f in fib]
        expected_faulted = _expected_faulted_evals(transcript_field, transcript_size)

        _, baseline_evals = run_clean(transcript_size)
        baseline_set = set(baseline_evals)

        for num_queries in args.queries:
            print(f"\n{'='*60}", flush=True)
            print(f"TRANSCRIPT_SIZE={transcript_size}  "
                  f"NUM_QUERIES={num_queries}", flush=True)
            print(f"{'='*60}", flush=True)

            print(f"  {'prob':>6}  {'runs':>5}  {'extracted':>10}  "
                  f"{'crashes':>8}  {'avg triggers':>13}", flush=True)
            print(f"  {'-'*50}", flush=True)

            for prob in args.probs:
                extracted      = 0
                crashes        = 0
                total_triggers = 0

                for _ in range(args.runs):
                    root, evals, triggers, crashed = run_fi(prob, transcript_size)
                    total_triggers += triggers

                    if crashed:
                        crashes += 1
                    else:
                        if try_extract(evals, transcript_size, expected_faulted,
                                       baseline_set, num_queries):
                            extracted += 1

                avg_triggers = total_triggers / args.runs
                print(f"  {prob:>6.1f}  {args.runs:>5}  {extracted:>10}  "
                      f"{crashes:>8}  {avg_triggers:>13.1f}", flush=True)

if __name__ == "__main__":
    main()
