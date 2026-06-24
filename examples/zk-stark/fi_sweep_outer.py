#!/usr/bin/env python3
"""
Fault injection sweep targeting the outer (len) loop back-edge of fft().

Skipping the len-loop back-edge causes fft() to return after completing only
the first stage (len=2 butterflies). All subsequent mixing stages are skipped.
This is a more aggressive corruption than the j-loop injection: pairs of
adjacent elements (after bit-reversal) are summed/differenced, but no
inter-group mixing occurs.
"""

import os
import re
import subprocess

# ── Field arithmetic (Mersenne prime p = 2^61 - 1) ──────────────────────────

P = (1 << 61) - 1

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

def _one_stage_fft(a, root):
    """
    FFT with only the first stage (len=2) executed.

    Simulates skipping the len-loop back-edge: bit_reverse runs, then only the
    len=2 butterfly stage executes before fft() returns. For len=2, half=1 and
    j=0 is the only iteration, so w=1 always and the butterfly is (u+v, u-v).
    The root argument is unused (w=1 throughout) but kept for interface parity.
    """
    n = len(a)
    a = _bit_reverse(a)
    for i in range(0, n, 2):
        u, v = a[i], a[i + 1]
        a[i]     = (u + v) % P
        a[i + 1] = (u + P - v) % P
    return a

def expected_leaked_set(transcript_size, transcript):
    """
    Simulate the one-stage broken IFFT + FFT pipeline and return the set of
    32-bit values that appear in the faulted evals output.
    On RV32 ILP32, printf("%lu") truncates uint64_t to 32 bits.
    """
    n      = transcript_size
    root   = pow(3, (P - 1) // n,       P)
    e_root = pow(3, (P - 1) // (2 * n), P)
    inv_r  = pow(root, P - 2, P)
    inv_n  = pow(n,    P - 2, P)

    # Broken IFFT: one-stage fft with inv_root, then scale by 1/n
    coeffs = _one_stage_fft(list(transcript), inv_r)
    coeffs = [(x * inv_n) % P for x in coeffs]

    # Broken forward FFT on zero-padded coefficients
    evals = _one_stage_fft(coeffs + [0] * n, e_root)

    return {x & 0xFFFFFFFF for x in evals}

EXAMPLE_DIR   = os.path.dirname(os.path.abspath(__file__))
PROBABILITIES = [round(i * 0.1, 1) for i in range(1, 11)]
RUNS_PER_PROB = 30
TRANSCRIPT_SIZES = [8, 16, 32, 64, 128, 256, 512, 1024]

# len-loop back-edge PC (fft_start + 0x4f8).
# transcript_size no longer affects the compiled binary (all arrays are now
# heap-allocated), so fft() is always at the same address for all sizes.
BACK_EDGE_PC = 0x11c2e

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

UINT64_MAX = (1 << 64)

def fibonacci(n):
    """Fibonacci with uint64_t wrapping to match C behaviour."""
    seq = [1, 1]
    for i in range(2, n):
        seq.append((seq[-1] + seq[-2]) % UINT64_MAX)
    return seq

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

def main():
    print("  building ... ", end="", flush=True)
    build()
    print("done")

    for transcript_size in TRANSCRIPT_SIZES:
        transcript = fibonacci(transcript_size)

        print(f"\n{'='*65}")
        print(f"TRANSCRIPT_SIZE={transcript_size}  back-edge PC={BACK_EDGE_PC:#x}")
        print(f"{'='*65}")

        baseline_root, baseline_evals = run_clean(transcript_size)
        baseline_eval_set = set(baseline_evals)
        print(f"  baseline root: {baseline_root}")

        leaked_expected = expected_leaked_set(transcript_size, transcript)
        detectable      = leaked_expected - baseline_eval_set
        print(f"  detectable leaked values: {len(detectable)}\n")

        print(f"  {'prob':>6}  {'runs':>5}  {'leaks':>6}  {'crashes':>8}  {'avg triggers':>13}")
        print(f"  {'-'*53}")

        for prob in PROBABILITIES:
            leaks          = 0
            crashes        = 0
            total_triggers = 0

            for _ in range(RUNS_PER_PROB):
                root, evals, triggers, crashed = run_fi(prob, transcript_size)
                total_triggers += triggers

                if crashed:
                    crashes += 1
                else:
                    if detectable & set(evals):
                        leaks += 1

            avg_triggers = total_triggers / RUNS_PER_PROB
            print(f"  {prob:>6.1f}  {RUNS_PER_PROB:>5}  {leaks:>6}  {crashes:>8}  {avg_triggers:>13.1f}")

if __name__ == "__main__":
    main()
