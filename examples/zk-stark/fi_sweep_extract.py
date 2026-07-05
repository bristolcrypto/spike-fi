#!/usr/bin/env python3
"""
Fault injection sweep targeting the inner (j) loop back-edge of fft().

Detection: optimistically assume the faults needed to isolate the last
input value occurred, invert the broken pipeline, and check if the
recovered value matches the public Fibonacci constraint.

Only log2(n)-1 specific faults are needed (one per stage at the group
containing position n-1), giving success probability ~p^(log2(n)-1)
— far higher than requiring the entire transform to be uniformly faulted.
"""

import os
import re
import subprocess
from math import log2

P = (1 << 61) - 1
UINT64_MAX = (1 << 64)

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

def _inv_fft_j0(a):
    """Inverse of the j=0-only FFT (all twiddle factors w=1)."""
    n = len(a); a = list(a)
    inv2 = pow(2, P - 2, P)
    length = n
    while length >= 2:
        half = length // 2
        for i in range(0, n, length):
            s, d = a[i], a[i + half]
            a[i]        = (s + d) * inv2 % P
            a[i + half] = (s + P - d) * inv2 % P
        length //= 2
    return _bit_reverse(a)

def try_extract(faulted_evals, transcript_size, transcript_field):
    """
    Invert the broken IFFT+FFT pipeline under the j=0 fault assumption,
    then check each position from n-1 (most likely) down to 0 (least
    likely) for a match against the public Fibonacci constraints.

    Returns the index of the first extracted position, or -1 if none.
    """
    n = transcript_size

    # Invert the broken forward FFT (2n elements)
    padded = _inv_fft_j0(list(faulted_evals))
    coeffs = padded[:n]

    # Undo the 1/n IFFT scaling
    scaled = [(c * n) % P for c in coeffs]

    # Invert the broken IFFT
    candidate = _inv_fft_j0(scaled)

    # Check positions from n-1 (easiest to fault) down to 0
    for i in range(n - 1, -1, -1):
        if candidate[i] == transcript_field[i]:
            return i
    return -1

# ── Sweep infrastructure ─────────────────────────────────────────────────────

EXAMPLE_DIR   = os.path.dirname(os.path.abspath(__file__))
PROBABILITIES = [round(i * 0.1, 1) for i in range(1, 11)]
RUNS_PER_PROB = 30
TRANSCRIPT_SIZES = [8, 16, 32, 64, 128, 256, 512, 1024]

# j-loop back-edge PC
BACK_EDGE_PC = 0x11c02

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

def run_fi(prob, transcript_size):
    spec = f"pc:{BACK_EDGE_PC:#x}:{prob:.1f}:s"
    r    = make("run", f"FI=--fi-enable --fi-debug --fi-spec={spec}",
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
        fib = fibonacci(transcript_size)
        transcript_field = [f % P for f in fib]

        print(f"\n{'='*60}", flush=True)
        print(f"TRANSCRIPT_SIZE={transcript_size}", flush=True)
        print(f"{'='*60}", flush=True)

        print(f"  {'prob':>6}  {'runs':>5}  {'extracted':>10}  "
              f"{'crashes':>8}  {'avg triggers':>13}", flush=True)
        print(f"  {'-'*50}", flush=True)

        for prob in PROBABILITIES:
            extracted      = 0
            crashes        = 0
            total_triggers = 0

            for _ in range(RUNS_PER_PROB):
                root, evals, triggers, crashed = run_fi(prob, transcript_size)
                total_triggers += triggers

                if crashed:
                    crashes += 1
                else:
                    pos = try_extract(evals, transcript_size, transcript_field)
                    if pos >= 0:
                        extracted += 1

            avg_triggers = total_triggers / RUNS_PER_PROB
            print(f"  {prob:>6.1f}  {RUNS_PER_PROB:>5}  {extracted:>10}  "
                  f"{crashes:>8}  {avg_triggers:>13.1f}", flush=True)

if __name__ == "__main__":
    main()
