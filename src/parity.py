"""
Outer Layer - XOR Parity Frames (frame-level erasure recovery).

Inner layer (Hamming(7,4) + depth-32 interleaving) repairs bursts of up to 32
bits per block *inside* one frame. A longer burst leaves some codewords with
2+ errors, the frame's CRC-16 fails, and the frame is lost.

The outer layer fixes that. For every group of k data frames the sender adds one
parity frame:

    P = F1 ^ F2 ^ ... ^ Fk        (byte-wise, on the 256-byte padded raw payloads)

The receiver uses CRC-16 to locate a bad frame (or a missing frame_id over UDP).
A known-position loss is an *erasure*, and one erasure per group can be solved:

    Fx = P ^ (all other frames of the group)

Limits: one bad frame per group. Two or more are detected (CRC-16 / SHA-256)
but cannot be repaired.
"""

from typing import Optional, Sequence, Tuple

from .framing import FRAME_PAYLOAD_SIZE


def xor_payloads(payloads: Sequence[bytes]) -> bytes:
    """Byte-wise XOR of equal-length payloads (each FRAME_PAYLOAD_SIZE bytes)."""
    if not payloads:
        raise ValueError("Need at least one payload")
    acc = 0
    for p in payloads:
        if len(p) != FRAME_PAYLOAD_SIZE:
            raise ValueError(f"Payload must be {FRAME_PAYLOAD_SIZE} bytes, got {len(p)}")
        acc ^= int.from_bytes(p, 'big')
    return acc.to_bytes(FRAME_PAYLOAD_SIZE, 'big')


def build_parity_payload(group_payloads: Sequence[bytes]) -> bytes:
    """Parity payload for one group of padded raw payloads."""
    return xor_payloads(group_payloads)


def rebuild_frame(group_payloads: Sequence[Optional[bytes]],
                  parity_payload: Optional[bytes]) -> Optional[Tuple[int, bytes]]:
    """
    Rebuild the single unknown frame of a group.

    group_payloads: padded raw payloads in group order; None marks a frame that
                    failed CRC or never arrived (an erasure).
    parity_payload: the group's parity payload, or None if it is unusable.

    Returns (index_in_group, rebuilt_payload), or None when recovery is
    impossible (not exactly one erasure, or no usable parity).
    """
    missing = [i for i, p in enumerate(group_payloads) if p is None]
    if len(missing) != 1 or parity_payload is None:
        return None
    known = [p for p in group_payloads if p is not None] + [parity_payload]
    return missing[0], xor_payloads(known)


def parity_test() -> bool:
    """Unit tests for the XOR parity layer."""
    import random
    print("Running parity layer test...")
    rng = random.Random(7)

    for k in (1, 2, 3, 4, 8):
        group = [bytes(rng.randrange(256) for _ in range(FRAME_PAYLOAD_SIZE)) for _ in range(k)]
        parity = build_parity_payload(group)
        assert xor_payloads(group + [parity]) == bytes(FRAME_PAYLOAD_SIZE)
        for lost in range(k):
            damaged = list(group)
            damaged[lost] = None
            result = rebuild_frame(damaged, parity)
            assert result == (lost, group[lost]), f"k={k} lost={lost}"
    print("  [PASS] Parity built and every single frame rebuilt for k = 1, 2, 3, 4, 8")

    group = [bytes(rng.randrange(256) for _ in range(FRAME_PAYLOAD_SIZE)) for _ in range(4)]
    parity = build_parity_payload(group)
    assert rebuild_frame(list(group), parity) is None
    assert rebuild_frame([None, None, group[2], group[3]], parity) is None
    assert rebuild_frame([None, group[1], group[2], group[3]], None) is None
    print("  [PASS] Recovery refused for 0 or 2+ erasures and for missing parity")

    print("\n  [PASS] All parity tests passed!")
    return True


if __name__ == "__main__":
    parity_test()
