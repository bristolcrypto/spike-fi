#!/usr/bin/env python3

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

def _fft_j0(a, root):
    """FFT with only j=0 butterfly per group (simulates the fault)."""
    n = len(a); a = _bit_reverse(a)
    length = 2
    while length <= n:
        half = length // 2
        for i in range(0, n, length):
            u, v = a[i], a[i + half]          # w = 1 always (j = 0)
            a[i]        = (u + v) % P
            a[i + half] = (u + P - v) % P
        length *= 2
    return a

def expected_leaked_set(transcript_size, transcript):
    """
    Simulate the j=0-only broken IFFT + FFT pipeline in Python and return
    the set of 32-bit values that appear in the faulted evals output.
    On RV32 ILP32, printf("%lu") truncates uint64_t to 32 bits.
    """
    n      = transcript_size
    root   = pow(3, (P - 1) // n,       P)
    e_root = pow(3, (P - 1) // (2 * n), P)
    inv_r  = pow(root, P - 2, P)
    inv_n  = pow(n,    P - 2, P)

    # Broken IFFT: fft with inv_root then scale by 1/n
    coeffs = _fft_j0(list(transcript), inv_r)
    coeffs = [(x * inv_n) % P for x in coeffs]

    # Broken 2nd FFT on zero-padded coefficients
    evals = _fft_j0(coeffs + [0] * n, e_root)

    return {x & 0xFFFFFFFF for x in evals}

EXAMPLE_DIR   = os.path.dirname(os.path.abspath(__file__))
PROBABILITIES = [round(i * 0.1, 1) for i in range(1, 11)]
RUNS_PER_PROB = 30

# j-loop back-edge PC (fft_start + 0x4cc) per transcript size.
# Derived from objdump of each build; fft() body is identical across sizes so
# the 0x4cc offset is stable — only the base address shifts with TRANSCRIPT_SIZE.
BACK_EDGE_PC = {
      8: 0x11bf0,
     16: 0x11e46,
     32: 0x11b0a,
     64: 0x11b10,
    128: 0x11ae8,
    256: 0x11aea,
    512: 0x11ae8,
   1024: 0x11b08,
}

def make(*args):
    return subprocess.run(
        ["make", *args],
        cwd=EXAMPLE_DIR,
        capture_output=True,
        text=True,
    )

def build(transcript_size):
    make("clean", f"TRANSCRIPT_SIZE={transcript_size}").check_returncode()
    make("build", f"TRANSCRIPT_SIZE={transcript_size}").check_returncode()

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

def run_clean():
    r = make("run")
    return parse_output(r.stdout + r.stderr)

def run_fi(prob, target_pc):
    spec = f"pc:{target_pc:#x}:{prob:.1f}:s"
    r    = make("run", f"FI=--fi-enable --fi-debug --fi-spec={spec}")
    text = r.stdout + r.stderr
    root, evals = parse_output(text)
    crashed  = root is None
    triggers = len(re.findall(r"trigger=1", text))
    return root, evals, triggers, crashed

def main():
    for transcript_size, back_edge_pc in BACK_EDGE_PC.items():
        transcript = fibonacci(transcript_size)

        print(f"\n{'='*65}")
        print(f"TRANSCRIPT_SIZE={transcript_size}  back-edge PC={back_edge_pc:#x}")
        print(f"{'='*65}")

        print("  building ... ", end="", flush=True)
        build(transcript_size)
        print("done")

        baseline_root, baseline_evals = run_clean()
        baseline_eval_set = set(baseline_evals)
        print(f"  baseline root: {baseline_root}")

        # Values that appear in evals under the j=0-only fault (32-bit truncated)
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
                root, evals, triggers, crashed = run_fi(prob, back_edge_pc)
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
