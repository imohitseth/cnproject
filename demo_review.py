"""
Live Review Demo - walks through the design's behaviour in five short scenarios.

Every scenario runs the real Client -> Relay -> Server pipeline over sockets
(TCP or UDP) on a 5-frame file. The relay is told exactly which frame to hit, so
the outcome is the same every time.

    python demo_review.py              # run all steps, condensed log
    python demo_review.py --pause      # wait for Enter between steps (for presenting)
    python demo_review.py --verbose    # show the full client/relay/server log
"""

import argparse
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import harness

KEEP = ("[Relay] Frame", "[Relay] UDP Frame", "[Server] Frame", "[Server] Parity", "Group ",
        "Layer 1", "Layer 2", "Bit errors", "Frames CRC", "Frames rebuilt", "Frames unrecoverable",
        "VERDICT", "Detected bad", "restored all data")

STEPS = [
    ("1. Burst WITHIN the interleaver depth (12 bits on frame #3)",
     "Hamming + depth-32 interleaving alone repairs it. CRC-16 passes; the parity frame is not needed.",
     dict(proto='tcp', min_burst=12, max_burst=12, target_frames='3')),
    ("2. Burst PAST the depth (40 bits on frame #3), parity OFF",
     "A codeword is hit twice, Hamming cannot fix it, CRC-16 flags the frame, SHA-256 mismatches: "
     "the failure is DETECTED and reported (never silent).",
     dict(proto='tcp', min_burst=40, max_burst=40, target_frames='3', group_size=0)),
    ("3. Same 40-bit burst on frame #3, XOR parity ON",
     "CRC-16 points at frame #3, the receiver rebuilds it as P1 ^ #1 ^ #2 ^ #4, re-checks the CRC "
     "and the file verifies. No retransmission.",
     dict(proto='tcp', min_burst=40, max_burst=40, target_frames='3')),
    ("4. Limit: TWO bad frames in one group (#2 and #3)",
     "One parity frame gives one equation per byte, so two unknown frames cannot be rebuilt. "
     "Detected and reported.",
     dict(proto='tcp', min_burst=40, max_burst=40, target_frames='2,3')),
    ("5. UDP: a whole frame is LOST (#2 dropped by the relay)",
     "A missing frame_id is a known-position erasure, so the parity frame repairs a lost datagram "
     "as well as a corrupted one.",
     dict(proto='udp', drop_frames='2', corruption_prob=0.0)),
]


def condensed(text: str) -> str:
    return "\n".join("  " + ln for ln in text.splitlines()
                     if any(k in ln for k in KEEP))


def main():
    ap = argparse.ArgumentParser(description='Live review demo')
    ap.add_argument('--pause', action='store_true', help='wait for Enter between steps')
    ap.add_argument('--verbose', action='store_true', help='show the full log of every step')
    args = ap.parse_args()

    summary = []
    print("\n" + "#" * 72)
    print("  ERROR DETECTION & CORRECTION - LIVE REVIEW DEMO")
    print("  Layer 1: Hamming(7,4) + bit interleaving (depth 32)   Layer 2: XOR parity frame")
    print("#" * 72)
    for title, why, kw in STEPS:
        if args.pause:
            input("\n[Enter] to run the next step... ")
        print("\n" + "=" * 72)
        print(title)
        print("  What to expect: " + why)
        print("=" * 72)
        kw = dict(kw)
        kw['seed'] = 11
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = harness.run_scenario(**kw)
        print(buf.getvalue() if args.verbose else condensed(buf.getvalue()))
        rep = result['report'] or {}
        summary.append((title.split(' (')[0], rep.get('match'),
                        rep.get('rebuilt', []), rep.get('unrecoverable', [])))

    print("\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    for name, ok, rebuilt, bad in summary:
        detail = (f"rebuilt {['#%d' % i for i in rebuilt]}" if rebuilt else
                  f"detected bad {['#%d' % i for i in bad]}" if bad else "layer 1 only")
        print(f"  {'PASS' if ok else 'FAIL':<5} {name:<58} {detail}")
    print("\n  FAIL here means: damage beyond the design envelope, caught by CRC-16 / SHA-256 and reported.")
    print("  Retransmission requests sent in every scenario: 0\n")


if __name__ == '__main__':
    main()
