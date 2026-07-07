#!/usr/bin/env python3
"""
Fault injection sweep on the recursive Cooley-Tukey NTT.

The attack skips the odd recursive call in fft().  When skipped, the odd
sub-array retains raw input values.  The combine step then mixes
transformed-even with raw-odd using known twiddle factors.  Inversion
recovers the raw odd-indexed inputs directly.

With the PC-based fault, the skip fires at EVERY recursion level: all
odd sub-calls are skipped.  The inversion accounts for this by
recursively extracting odd values at each level.

At p=1.0 the entire transcript is recoverable.  At p<1.0 individual
positions are checked against the public Fibonacci constraints.
"""

import argparse
import os
import re
import random
import subprocess

P = (1 << 61) - 1
UINT64_MAX = (1 << 64)

EXAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))

# PC of "jal fft.part.0" for the odd recursive call (after FI_MARK).
BACK_EDGE_PC = 0x110cc

def _inv_fft_odd_skip(a, root):
    """
    Inverse of recursive FFT with all odd sub-calls skipped.

    At each level: undo the combine step to recover even_result and
    odd_raw, then recursively invert even_result.  odd_raw values are
    the raw inputs at odd positions (they were never transformed).
    """
    n = len(a)
    if n <= 1:
        return list(a)

    half = n // 2
    inv2 = pow(2, P - 2, P)

    # Undo combine: a[j] = even[j] + w^j*odd[j],  a[j+half] = even[j] - w^j*odd[j]
    even_result = [0] * half
    odd_raw     = [0] * half
    w = 1
    for j in range(half):
        s = a[j]
        d = a[j + half]
        even_result[j] = (s + d) * inv2 % P
        v = (s + P - d) * inv2 % P
        odd_raw[j] = v * pow(w, P - 2, P) % P
        w = w * root % P

    # Recursively invert the even sub-result (also had odd calls skipped)
    w2 = root * root % P
    even_input = _inv_fft_odd_skip(even_result, w2)

    # Interleave: even positions from recursion, odd positions are raw
    result = [0] * n
    for i in range(half):
        result[2 * i]     = even_input[i]
        result[2 * i + 1] = odd_raw[i]
    return result

def _fft_odd_skip(a, root):
    """Forward recursive FFT with all odd sub-calls skipped."""
    n = len(a)
    if n <= 1:
        return list(a)
    half = n // 2
    even = [a[2*i] for i in range(half)]
    odd  = [a[2*i+1] for i in range(half)]
    w2 = root * root % P
    even_result = _fft_odd_skip(even, w2)
    result = [0] * n
    w = 1
    for j in range(half):
        t = odd[j] * w % P
        result[j]        = (even_result[j] + t) % P
        result[j + half] = (even_result[j] + P - t) % P
        w = w * root % P
    return result

def _expected_faulted_evals(transcript_field, transcript_size):
    n      = transcript_size
    root   = pow(3, (P - 1) // n, P)
    e_root = pow(3, (P - 1) // (2 * n), P)
    inv_root = pow(root, P - 2, P)
    inv_n  = pow(n, P - 2, P)
    coeffs = _fft_odd_skip(list(transcript_field), inv_root)
    coeffs = [(x * inv_n) % P for x in coeffs]
    return _fft_odd_skip(coeffs + [0] * n, e_root)

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
    make("build", "TEST_SRC=test_recursive.c").check_returncode()

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
    ap = argparse.ArgumentParser(description="Recursive CT loop-skip FI sweep")
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
