"""
Burst-Length Sweep - evidence for the design envelope.

For each burst length it injects a contiguous burst into a protected group of
frames and records how often the original data is recovered, for four
configurations:

  1. Hamming only                (no interleaving)
  2. + Interleave, depth 32      (the Review-1 design)
  3. + Interleave, depth 512     (whole frame = one block)
  4. depth 32 + XOR parity       (the design in the Review-2 deck: 4 data frames + 1 parity frame)
  5. depth 512 + XOR parity      (recommended tuning: both layers at full strength)

Every trial runs the real encode/corrupt/decode code (hamming.py, interleaver.py,
detection.py, parity.py); only the sockets are skipped, so thousands of trials run
in seconds. The run is reproducible with --seed.

Burst models
  single : the burst lands inside ONE random data frame (what the relay does per frame)
  stream : the burst lands anywhere in the concatenated frames of the group, so a long
           burst can spill over into the next frame (the worst case for the XOR layer)

Usage:
    python sweep.py [--trials 200] [--seed 1] [--model single|stream|both]
                    [--bursts 1,4,32,33,224] [--csv results/sweep_results.csv]
                    [--plot results/sweep.png]
"""

import argparse
import csv
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import hamming, interleaver, parity, detection
from src.channel_emulator import ChannelEmulator
from src.framing import FRAME_PAYLOAD_SIZE

DEFAULT_BURSTS = [1, 2, 4, 8, 16, 32, 33, 48, 64, 128, 224, 448, 500, 512, 513, 1000]
GROUP_SIZE = 4

# (label, interleave depth or None, uses XOR parity)
CONFIGS = [
    ("Hamming only", None, False),
    ("+ Interleave d=32", 32, False),
    ("+ Interleave d=512", 512, False),
    ("d=32 + XOR parity", 32, True),
    ("d=512 + XOR parity", 512, True),
]


def encode_wire(raw: bytes, depth):
    encoded = hamming.encode_bytes(raw)
    return encoded if depth is None else interleaver.interleave_bytes(encoded, depth)


def decode_wire(wire: bytes, depth) -> bytes:
    if depth is not None:
        wire = interleaver.deinterleave_bytes(wire, interleaver.CODEWORDS_PER_FRAME, depth)
    return hamming.decode_bytes(wire, interleaver.NIBBLES_PER_FRAME)[0]


class Group:
    """One protected group: k data frames (+ parity frame) as raw payloads and wire bytes."""

    def __init__(self, rng: random.Random, depth, use_parity: bool):
        self.depth = depth
        self.use_parity = use_parity
        self.raw = [bytes(rng.randrange(256) for _ in range(FRAME_PAYLOAD_SIZE))
                    for _ in range(GROUP_SIZE)]
        if use_parity:
            self.raw.append(parity.build_parity_payload(self.raw))
        self.wire = [encode_wire(r, depth) for r in self.raw]
        self.crc = [detection.crc16_ccitt(r) for r in self.raw]

    def recovered(self, wires):
        """
        Receiver logic on the (possibly corrupted) wires.
        Returns (success, silent) where `silent` means a frame was wrong but its CRC-16 passed.
        """
        decoded, bad, silent = [], [], False
        for i, w in enumerate(wires):
            d = self.raw[i] if w == self.wire[i] else decode_wire(w, self.depth)
            decoded.append(d)
            if d != self.raw[i]:
                if detection.crc16_ccitt(d) == self.crc[i]:
                    silent = True            # CRC missed it: frame looks fine but is wrong
                else:
                    bad.append(i)
        if silent:
            return False, True
        data_bad = [i for i in bad if i < GROUP_SIZE]
        if not data_bad:
            return True, False               # every data frame intact (parity damage is irrelevant)
        if self.use_parity and len(data_bad) == 1 and (GROUP_SIZE not in bad):
            known = [None if i == data_bad[0] else decoded[i] for i in range(GROUP_SIZE)]
            idx, rebuilt = parity.rebuild_frame(known, decoded[GROUP_SIZE])
            return rebuilt == self.raw[idx], False
        return False, False


def run_trial(group: Group, burst: int, model: str, rng: random.Random, emu: ChannelEmulator) -> tuple:
    wires = list(group.wire)
    if model == 'single':
        f = rng.randrange(GROUP_SIZE)                      # a data frame
        bits = len(wires[f]) * 8
        if burst > bits:
            return False, False
        wires[f] = emu.corrupt_at(wires[f], rng.randint(0, bits - burst), burst)
    else:                                                   # stream
        big = b''.join(wires)
        bits = len(big) * 8
        if burst > bits:
            return False, False
        big = emu.corrupt_at(big, rng.randint(0, bits - burst), burst)
        size = len(wires[0])
        wires = [big[i * size:(i + 1) * size] for i in range(len(wires))]
    return group.recovered(wires)


def sweep(bursts, trials, model, seed):
    rng = random.Random(seed)
    emu = ChannelEmulator()
    groups = {name: Group(rng, depth, par) for name, depth, par in CONFIGS}
    rows = []
    for b in bursts:
        for name, _, _ in CONFIGS:
            ok = silent = 0
            for _ in range(trials):
                s, sil = run_trial(groups[name], b, model, rng, emu)
                ok += s
                silent += sil
            rows.append({'model': model, 'burst_bits': b, 'config': name, 'trials': trials,
                         'recovered': ok, 'percent': 100.0 * ok / trials, 'silent_corruption': silent})
    return rows


def print_table(rows, bursts, model):
    names = [c[0] for c in CONFIGS]
    title = {'single': 'burst inside one random data frame',
             'stream': 'burst anywhere in the group stream (may span frames)'}[model]
    print(f"\nRecovery rate (%) - model: {title}")
    print(f"{'Burst (bits)':>12} | " + " | ".join(f"{n:>20}" for n in names))
    print("-" * (15 + 23 * len(names)))
    for b in bursts:
        cells = []
        for n in names:
            r = next(x for x in rows if x['burst_bits'] == b and x['config'] == n)
            cells.append(f"{r['percent']:>19.0f}%")
        print(f"{b:>12} | " + " | ".join(cells))
    silent = sum(r['silent_corruption'] for r in rows)
    print(f"\nSilent corruption events (CRC-16 passed on a wrong frame): {silent}")


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[sweep] results written to {path}")


def write_plot(path, rows, bursts, models):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("[sweep] matplotlib not installed - skipping plot (pip install matplotlib)")
        return
    fig, axes = plt.subplots(1, len(models), figsize=(6.8 * len(models), 4.4), squeeze=False)
    for ax, model in zip(axes[0], models):
        for name, _, _ in CONFIGS:
            ys = [next(r['percent'] for r in rows if r['model'] == model and r['burst_bits'] == b
                       and r['config'] == name) for b in bursts]
            ax.plot(range(len(bursts)), ys, marker='o', label=name)
        ax.axvline(bursts.index(32) + 0.5 if 32 in bursts else 0, color='grey', ls=':', lw=1)
        ax.set_xticks(range(len(bursts)))
        ax.set_xticklabels(bursts, rotation=45)
        ax.set_ylim(-5, 105)
        ax.set_xlabel("Burst length (bits)")
        ax.set_ylabel("Data recovered (%)")
        ax.set_title("Burst inside one frame" if model == 'single' else "Burst anywhere in group stream")
        ax.grid(alpha=0.3)
    axes[0][0].legend(fontsize=8, loc='lower left')
    fig.tight_layout()
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    fig.savefig(path, dpi=150)
    print(f"[sweep] plot written to {path}")


def main():
    ap = argparse.ArgumentParser(description='Burst-length sweep over the protection layers')
    ap.add_argument('--trials', type=int, default=200, help='trials per cell (default 200)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--model', choices=['single', 'stream', 'both'], default='both')
    ap.add_argument('--bursts', default=','.join(map(str, DEFAULT_BURSTS)))
    ap.add_argument('--csv', default=os.path.join('results', 'sweep_results.csv'))
    ap.add_argument('--plot', default=os.path.join('results', 'sweep.png'), help="PNG path, or '' to skip")
    args = ap.parse_args()

    bursts = [int(x) for x in args.bursts.split(',')]
    models = ['single', 'stream'] if args.model == 'both' else [args.model]
    print(f"[sweep] {args.trials} trials per cell, seed {args.seed}, bursts {bursts}")
    t0 = time.time()
    all_rows = []
    for m in models:
        rows = sweep(bursts, args.trials, m, args.seed)
        print_table(rows, bursts, m)
        all_rows.extend(rows)
    print(f"\n[sweep] done in {time.time() - t0:.1f} s")
    if args.csv:
        write_csv(args.csv, all_rows)
    if args.plot:
        write_plot(args.plot, all_rows, bursts, models)


if __name__ == '__main__':
    main()
