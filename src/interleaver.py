"""
Bit-Level Block Interleaver for Burst Error Recovery.

Hamming(7,4) is a Single-Error-Correcting (SEC) code that can only correct
1 bit flip per 7-bit codeword. In practical channels, errors often occur in bursts
(e.g., electromagnetic interference, lightning, transient noise) corrupting
consecutive bits.

Block interleaving rearranges bits so that consecutive bits in the transmitted stream
belong to different codewords. With depth D = 32:
- Codewords are arranged into blocks of 32 codewords (32 * 7 bits = 224 bits = 28 bytes).
- Bits are transmitted column-by-column instead of row-by-row.
- A contiguous burst of length L <= 32 bits will affect at most 1 bit in any single codeword.
- The receiver de-interleaves the stream back to row-by-row order, transforming the
  burst into isolated single-bit errors across multiple codewords.
- Hamming(7,4) SEC can then correct 100% of these errors without retransmission!

Frame Configuration:
  Raw payload: 256 bytes = 512 nibbles
  Hamming(7,4) codewords: 512 codewords
  Interleave depth: 32 codewords per block
  Blocks per frame: 512 / 32 = 16 blocks
  Bits per block: 32 * 7 = 224 bits = 28 bytes
  Total encoded & interleaved payload: 16 * 28 = 448 bytes
"""

from typing import List, Tuple
import math

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Architecture Constants (from cn final.pdf)
INTERLEAVE_DEPTH = 32           # Codewords per block
BITS_PER_CODEWORD = 7          # Hamming(7,4) codeword length
CODEWORDS_PER_FRAME = 512      # 256 bytes = 512 nibbles = 512 codewords
NIBBLES_PER_FRAME = 512
BLOCKS_PER_FRAME = 16          # 512 / 32 = 16 blocks
BITS_PER_BLOCK = 224           # 32 * 7 = 224 bits
BYTES_PER_BLOCK = 28           # 224 / 8 = 28 bytes
ENCODED_PAYLOAD_SIZE = 448     # 16 * 28 = 448 bytes
RAW_PAYLOAD_SIZE = 256         # 256 bytes

# Depth must divide 512 (no short last block) and be a multiple of 8
# (depth * 7 bits is then a whole number of bytes per block).
VALID_DEPTHS = (8, 16, 32, 64, 128, 256, 512)


def validate_depth(depth: int) -> int:
    """Return `depth` if it is a supported interleave depth, else raise ValueError."""
    if depth not in VALID_DEPTHS:
        raise ValueError(f"Unsupported interleave depth {depth}; choose one of {VALID_DEPTHS}")
    return depth


def bytes_to_bits(data: bytes) -> List[int]:
    """Convert bytes to a list of bits (MSB to LSB)."""
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_bytes(bits: List[int]) -> bytes:
    """Convert a list of bits (MSB to LSB) to bytes, zero-padded at end if needed."""
    result = bytearray()
    pad_len = (8 - (len(bits) % 8)) % 8
    padded_bits = bits + [0] * pad_len
    for i in range(0, len(padded_bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | padded_bits[i + j]
        result.append(byte)
    return bytes(result)


def interleave_codewords(codewords: List[List[int]], depth: int = INTERLEAVE_DEPTH) -> List[int]:
    """
    Interleave a list of 7-bit Hamming codewords using block interleaving with depth D.
    """
    if not codewords:
        return []
    
    total_codewords = len(codewords)
    num_blocks = math.ceil(total_codewords / depth)
    interleaved_bits = []
    
    for b in range(num_blocks):
        block_cws = codewords[b * depth : min((b + 1) * depth, total_codewords)]
        actual_depth = len(block_cws)
        
        # Interleave column-by-column: column 0..6
        for col in range(BITS_PER_CODEWORD):
            for row in range(actual_depth):
                interleaved_bits.append(block_cws[row][col])
                
    return interleaved_bits


def deinterleave_bits(interleaved_bits: List[int], depth: int = INTERLEAVE_DEPTH, 
                      total_codewords: int = CODEWORDS_PER_FRAME) -> List[List[int]]:
    """
    De-interleave a stream of bits back into a list of 7-bit Hamming codewords.
    """
    num_blocks = math.ceil(total_codewords / depth)
    codewords = []
    bit_idx = 0
    
    for b in range(num_blocks):
        block_size = min(depth, total_codewords - b * depth)
        block_total_bits = block_size * BITS_PER_CODEWORD
        
        if bit_idx + block_total_bits > len(interleaved_bits):
            break
            
        block_bits = interleaved_bits[bit_idx : bit_idx + block_total_bits]
        bit_idx += block_total_bits
        
        block_cws = [[0] * BITS_PER_CODEWORD for _ in range(block_size)]
        for col in range(BITS_PER_CODEWORD):
            for row in range(block_size):
                block_cws[row][col] = block_bits[col * block_size + row]
                
        codewords.extend(block_cws)
        
    return codewords


def interleave_bytes(encoded_bytes: bytes, depth: int = INTERLEAVE_DEPTH) -> bytes:
    """
    Take Hamming(7,4) encoded bytes, unpack into codewords, 
    perform block interleaving with depth D, and repack into bytes.
    """
    bits = bytes_to_bits(encoded_bytes)
    num_codewords = len(bits) // BITS_PER_CODEWORD
    codewords = []
    for i in range(num_codewords):
        codewords.append(bits[i * BITS_PER_CODEWORD : (i + 1) * BITS_PER_CODEWORD])
        
    interleaved_bits = interleave_codewords(codewords, depth=depth)
    return bits_to_bytes(interleaved_bits)


def deinterleave_bytes(interleaved_bytes: bytes, total_codewords: int = CODEWORDS_PER_FRAME, 
                       depth: int = INTERLEAVE_DEPTH) -> bytes:
    """
    Take interleaved bytes from the channel, de-interleave the bits back into
    sequential 7-bit Hamming codewords, and repack into bytes.
    """
    bits = bytes_to_bits(interleaved_bytes)
    codewords = deinterleave_bits(bits, depth=depth, total_codewords=total_codewords)
    
    cw_bits = []
    for cw in codewords:
        cw_bits.extend(cw)
        
    return bits_to_bytes(cw_bits)


def interleaver_test() -> bool:
    """Test interleaver correctness and burst recovery capability."""
    print("Testing interleaver...")
    import random
    from . import hamming

    random.seed(42)
    orig_data = bytes([random.randint(0, 255) for _ in range(RAW_PAYLOAD_SIZE)])
    
    encoded = hamming.encode_bytes(orig_data)
    assert len(encoded) == ENCODED_PAYLOAD_SIZE
    
    interleaved = interleave_bytes(encoded, INTERLEAVE_DEPTH)
    assert len(interleaved) == ENCODED_PAYLOAD_SIZE
    
    # 1. Clean round-trip
    deinterleaved = deinterleave_bytes(interleaved, CODEWORDS_PER_FRAME, INTERLEAVE_DEPTH)
    decoded, n_corr, n_det = hamming.decode_bytes(deinterleaved, NIBBLES_PER_FRAME)
    assert decoded == orig_data
    assert n_corr == 0
    print("  [PASS] Clean roundtrip passed")
    
    # 2. Burst error up to 32 bits
    for burst_len in [1, 4, 8, 16, 24, 32]:
        corrupted = bytearray(interleaved)
        start_bit = 100
        for b in range(burst_len):
            byte_idx = (start_bit + b) // 8
            bit_idx = 7 - ((start_bit + b) % 8)
            corrupted[byte_idx] ^= (1 << bit_idx)
            
        deint = deinterleave_bytes(bytes(corrupted), CODEWORDS_PER_FRAME, INTERLEAVE_DEPTH)
        dec, n_corr, n_det = hamming.decode_bytes(deint, NIBBLES_PER_FRAME)
        
        assert dec == orig_data
        assert n_corr == burst_len
        print(f"  [PASS] Burst error of {burst_len} bits: 100% recovered ({n_corr} errors corrected)")
        
    # 3. Depth sweep: any burst up to the depth is fully corrected, for every valid depth
    for depth in VALID_DEPTHS:
        inter = interleave_bytes(encoded, depth)
        assert len(inter) == ENCODED_PAYLOAD_SIZE
        for burst_len in sorted({1, depth // 2, depth}):
            for start_bit in (0, 100, 224 - burst_len // 2, ENCODED_PAYLOAD_SIZE * 8 - burst_len):
                corrupted = bytearray(inter)
                for b in range(burst_len):
                    pos = start_bit + b
                    corrupted[pos // 8] ^= 1 << (7 - pos % 8)
                deint = deinterleave_bytes(bytes(corrupted), CODEWORDS_PER_FRAME, depth)
                dec, _, _ = hamming.decode_bytes(deint, NIBBLES_PER_FRAME)
                assert dec == orig_data, f"depth={depth} burst={burst_len} start={start_bit}"
    print(f"  [PASS] Depths {VALID_DEPTHS}: bursts up to the depth recovered at every position")

    # 4. One bit past the depth, inside a single block, is NOT recoverable
    corrupted = bytearray(interleaved)
    for b in range(INTERLEAVE_DEPTH + 1):
        pos = 10 + b
        corrupted[pos // 8] ^= 1 << (7 - pos % 8)
    deint = deinterleave_bytes(bytes(corrupted), CODEWORDS_PER_FRAME, INTERLEAVE_DEPTH)
    dec, _, _ = hamming.decode_bytes(deint, NIBBLES_PER_FRAME)
    assert dec != orig_data
    print("  [PASS] Burst of depth+1 inside one block exceeds Hamming (limit confirmed)")

    print("  [PASS] All interleaver tests passed!")
    return True


if __name__ == "__main__":
    interleaver_test()
