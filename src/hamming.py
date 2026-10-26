"""
Hamming(7,4) Single-Error-Correcting Code Implementation.

Encodes 4-bit nibbles into 7-bit codewords using 3 parity bits.
Bit positions (1-indexed): p1=1, p2=2, d1=3, p3=4, d2=5, d3=6, d4=7

Parity coverage:
  p1 covers positions {1,3,5,7} = {p1, d1, d2, d4}
  p2 covers positions {2,3,6,7} = {p2, d1, d3, d4}
  p3 covers positions {4,5,6,7} = {p3, d2, d3, d4}

Syndrome calculation:
  c1 = p1 XOR d1 XOR d2 XOR d4
  c2 = p2 XOR d1 XOR d3 XOR d4
  c3 = p3 XOR d2 XOR d3 XOR d4
  error_pos = c1 | (c2 << 1) | (c3 << 2)  [1-indexed; 0 means no error]
"""

from typing import Tuple, List, Union


def _nibble_to_bits(nibble: int) -> List[int]:
    """Convert a 4-bit integer to a list of 4 bits [d1, d2, d3, d4]."""
    return [(nibble >> i) & 1 for i in range(4)]


def _bits_to_nibble(bits: List[int]) -> int:
    """Convert a list of 4 bits [d1, d2, d3, d4] to a 4-bit integer."""
    return bits[0] | (bits[1] << 1) | (bits[2] << 2) | (bits[3] << 3)


def encode_nibble(nibble: int) -> List[int]:
    """
    Encode a 4-bit nibble (0-15) into a 7-bit Hamming codeword.
    Returns list of 7 bits: [p1, p2, d1, p3, d2, d3, d4]
    """
    if not (0 <= nibble <= 15):
        raise ValueError(f"nibble must be 0-15, got {nibble}")
    
    d1, d2, d3, d4 = _nibble_to_bits(nibble)
    
    # Compute parity bits
    p1 = d1 ^ d2 ^ d4
    p2 = d1 ^ d3 ^ d4
    p3 = d2 ^ d3 ^ d4
    
    return [p1, p2, d1, p3, d2, d3, d4]


def encode_nibble_int(nibble: int) -> int:
    """Encode nibble to 7-bit integer (MSB = position 1)."""
    bits = encode_nibble(nibble)
    result = 0
    for b in bits:
        result = (result << 1) | b
    return result


def decode_codeword(codeword: List[int]) -> Tuple[int, int, bool]:
    """
    Decode a 7-bit Hamming codeword, correcting single-bit errors.
    Returns: (nibble, error_pos, was_corrected)
    """
    if len(codeword) != 7:
        raise ValueError(f"codeword must have 7 bits, got {len(codeword)}")
    
    p1, p2, d1, p3, d2, d3, d4 = codeword
    
    # Compute syndrome bits
    c1 = p1 ^ d1 ^ d2 ^ d4
    c2 = p2 ^ d1 ^ d3 ^ d4
    c3 = p3 ^ d2 ^ d3 ^ d4
    
    # Syndrome gives 1-indexed error position
    error_pos = c1 | (c2 << 1) | (c3 << 2)
    
    was_corrected = False
    if error_pos != 0:
        codeword[error_pos - 1] ^= 1
        was_corrected = True
        p1, p2, d1, p3, d2, d3, d4 = codeword
    
    nibble = _bits_to_nibble([d1, d2, d3, d4])
    return nibble, error_pos, was_corrected


def decode_codeword_int(codeword_int: int) -> Tuple[int, int, bool]:
    """Decode a 7-bit integer codeword."""
    bits = [(codeword_int >> (6 - i)) & 1 for i in range(7)]
    return decode_codeword(bits)


def encode_bytes(data: bytes) -> bytes:
    """
    Encode a byte string using Hamming(7,4).
    Each byte = 2 nibbles = 2 codewords = 14 bits.
    """
    codeword_bits = []
    for byte in data:
        high_nibble = (byte >> 4) & 0x0F
        low_nibble = byte & 0x0F
        codeword_bits.extend(encode_nibble(high_nibble))
        codeword_bits.extend(encode_nibble(low_nibble))
    
    while len(codeword_bits) % 8 != 0:
        codeword_bits.append(0)
    
    result = bytearray()
    for i in range(0, len(codeword_bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | codeword_bits[i + j]
        result.append(byte)
    
    return bytes(result)


def decode_bytes(encoded: bytes, expected_nibbles: int, return_details: bool = False):
    """
    Decode Hamming(7,4) encoded bytes.
    If return_details is True, also returns list of (codeword_index, error_pos).
    """
    bits = []
    for byte in encoded:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    
    nibbles = []
    total_corrected = 0
    total_detected = 0
    repair_details = []
    idx = 0
    
    for cw_idx in range(expected_nibbles):
        if idx + 7 > len(bits):
            break
        codeword = bits[idx:idx + 7]
        nibble, error_pos, was_corrected = decode_codeword(codeword)
        nibbles.append(nibble)
        if was_corrected:
            total_corrected += 1
            total_detected += 1
            repair_details.append((cw_idx, error_pos))
        idx += 7
    
    result = bytearray()
    for i in range(0, len(nibbles) - 1, 2):
        byte = (nibbles[i] << 4) | nibbles[i + 1]
        result.append(byte)
    
    if return_details:
        return bytes(result), total_corrected, total_detected, repair_details
    return bytes(result), total_corrected, total_detected


def exhaustive_test() -> bool:
    """Exhaustively test Hamming(7,4) across all 16 nibbles * 7 bit positions."""
    print("Running exhaustive Hamming(7,4) test...")
    print("  Testing all 16 nibbles * 7 single-bit flips + no-error case")
    
    all_passed = True
    for nibble in range(16):
        codeword = encode_nibble(nibble)
        
        # Test no-error case
        decoded, error_pos, was_corrected = decode_codeword(list(codeword))
        if decoded != nibble or error_pos != 0 or was_corrected:
            all_passed = False
        
        # Test each single-bit flip
        for pos in range(7):
            corrupted = list(codeword)
            corrupted[pos] ^= 1
            decoded, error_pos, was_corrected = decode_codeword(corrupted)
            expected_pos = pos + 1
            if decoded != nibble or error_pos != expected_pos or not was_corrected:
                all_passed = False
    
    if all_passed:
        print("  [PASS] All 16 * 8 = 128 test cases passed!")
    else:
        print("  [FAIL] Some tests failed!")
    
    return all_passed


if __name__ == "__main__":
    exhaustive_test()
