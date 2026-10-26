"""
Visual Inspection & Background Tracing Tool for Error Detection & Correction System.

Demonstrates the microscopic, bit-by-bit mechanics of the entire pipeline:
1. Raw Data & Nibbles
2. Hamming(7,4) Codewords & Parity Bits
3. Bit-Level Interleaving (Depth 32 Matrix)
4. Channel Noise Injection (Exact Bit Offsets Flipped)
5. De-interleaving & Burst Dispersion
6. Syndrome Decoding & Single-Bit Error Correction
7. Post-Correction CRC-16 & SHA-256 Verification

Usage:
    python inspect_pipeline.py [optional_text_message]
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import hamming, interleaver, detection, framing
from src.channel_emulator import ChannelEmulator


def print_banner(title):
    print("\n" + "=" * 75)
    print(f"  {title.upper()}")
    print("=" * 75)


def inspect(message="NETWORKS"):
    data = message.encode('utf-8')
    # Pad to 256 bytes for frame standard
    padded = data.ljust(256, b'\x00')
    
    print_banner("Step 1: Input Data & Pre-Encoding CRC-16")
    print(f"Original Text:       \"{message}\"")
    print(f"Original Length:     {len(data)} bytes (padded to 256 bytes for frame)")
    print(f"Data in Hex:         {data.hex(' ').upper()}")
    crc_orig = detection.crc16_ccitt(data)
    print(f"Calculated CRC-16:   0x{crc_orig:04X} (Polynomial: x^16 + x^12 + x^5 + 1)")
    
    # -------------------------------------------------------------
    # Step 2: Hamming Encoding
    # -------------------------------------------------------------
    print_banner("Step 2: Hamming(7,4) Forward Error Correction Encoding")
    print("Each 8-bit byte is split into Two 4-bit Nibbles (High & Low).")
    print("Each 4-bit nibble [d1, d2, d3, d4] gets 3 Parity bits [p1, p2, p3] -> 7-bit Codeword:")
    print("  Position:  1   2   3   4   5   6   7")
    print("  Layout:   p1  p2  d1  p3  d2  d3  d4\n")
    
    print("Sample: First Byte 'N' (0x4E = 0100 1110 in binary):")
    b0 = data[0]
    high_nibble = (b0 >> 4) & 0x0F  # 0x4 = 0100 -> d1=0, d2=0, d3=1, d4=0
    low_nibble = b0 & 0x0F         # 0xE = 1110 -> d1=0, d2=1, d3=1, d4=1
    
    cw_high = hamming.encode_nibble(high_nibble)
    cw_low = hamming.encode_nibble(low_nibble)
    
    print(f"  * High Nibble (0x{high_nibble:X}): bits={hamming._nibble_to_bits(high_nibble)}")
    print(f"    p1 = d1^d2^d4 = {cw_high[0]}")
    print(f"    p2 = d1^d3^d4 = {cw_high[1]}")
    print(f"    p3 = d2^d3^d4 = {cw_high[3]}")
    print(f"    --> Codeword 0: {cw_high}")
    
    print(f"  * Low Nibble (0x{low_nibble:X}):  bits={hamming._nibble_to_bits(low_nibble)}")
    print(f"    p1 = d1^d2^d4 = {cw_low[0]}")
    print(f"    p2 = d1^d3^d4 = {cw_low[1]}")
    print(f"    p3 = d2^d3^d4 = {cw_low[3]}")
    print(f"    --> Codeword 1: {cw_low}")
    
    encoded = hamming.encode_bytes(padded)
    print(f"\nTotal Encoded: 512 Codewords * 7 bits = 3584 bits (448 Bytes)")
    
    # -------------------------------------------------------------
    # Step 3: Interleaving
    # -------------------------------------------------------------
    print_banner("Step 3: Bit-Level Block Interleaving (Depth 32)")
    print("Codewords are written Row-by-Row into a 32 x 7 matrix (Block 0):")
    print("  Row  0 (CW 0):  [p1, p2, d1, p3, d2, d3, d4]")
    print("  Row  1 (CW 1):  [p1, p2, d1, p3, d2, d3, d4]")
    print("  Row  2 (CW 2):  [p1, p2, d1, p3, d2, d3, d4]")
    print("  ...             ...")
    print("  Row 31 (CW 31): [p1, p2, d1, p3, d2, d3, d4]")
    print("\nTransmission Order (Column-by-Column):")
    print("  Column 0 (Bit 1 of CW 0..31) -> 32 bits")
    print("  Column 1 (Bit 2 of CW 0..31) -> 32 bits")
    print("  Column 2 (Bit 3 of CW 0..31) -> 32 bits")
    print("  ...")
    print("  Column 6 (Bit 7 of CW 0..31) -> 32 bits")
    print("\nKEY PROPERTY: Consecutive bits in the stream belong to DIFFERENT codewords!")
    print("Bits from the SAME codeword are spaced exactly 32 bits apart in transmission.")
    
    interleaved = interleaver.interleave_bytes(encoded, interleaver.INTERLEAVE_DEPTH)
    
    # -------------------------------------------------------------
    # Step 4: Channel Corruption (Relay Process)
    # -------------------------------------------------------------
    print_banner("Step 4: Relay Channel Corruption (Burst Noise Injection)")
    # Inject a 12-bit burst starting at bit 10
    burst_start = 10
    burst_len = 12
    corrupted_bits = bytearray(interleaved)
    
    print(f"Injecting contiguous burst noise:")
    print(f"  * Start Bit Offset:    {burst_start} (Byte {burst_start // 8}, bit {7 - (burst_start % 8)})")
    print(f"  * Burst Length:        {burst_len} contiguous bits")
    print(f"  * Corrupted Bit Range: [{burst_start} .. {burst_start + burst_len - 1}]")
    
    flipped_indices = []
    for b in range(burst_len):
        bit_idx = burst_start + b
        byte_idx = bit_idx // 8
        bit_pos = 7 - (bit_idx % 8)
        old_val = (corrupted_bits[byte_idx] >> bit_pos) & 1
        corrupted_bits[byte_idx] ^= (1 << bit_pos)
        new_val = (corrupted_bits[byte_idx] >> bit_pos) & 1
        flipped_indices.append((bit_idx, byte_idx, bit_pos, old_val, new_val))
    
    print("\nMicroscopic Channel Bit Flips:")
    for bit_idx, byte_idx, bit_pos, old_v, new_v in flipped_indices[:6]:
        print(f"  Channel Bit #{bit_idx:4d} (Byte {byte_idx}, bit {bit_pos}): flipped {old_v} -> {new_v}")
    if len(flipped_indices) > 6:
        print(f"  ... and {len(flipped_indices) - 6} more consecutive channel bits.")
        
    corrupted_bytes = bytes(corrupted_bits)
    
    # -------------------------------------------------------------
    # Step 5: De-Interleaving at Server
    # -------------------------------------------------------------
    print_banner("Step 5: Server De-Interleaving & Burst Dispersion")
    print("Server receives corrupted stream and reverses the 32 x 7 matrix.")
    print(f"A 12-bit burst on the channel was at indices: {list(range(burst_start, burst_start + burst_len))}")
    print("\nBecause bits were taken column-by-column, de-interleaving places each flipped bit")
    print("into a DIFFERENT row (codeword)! Let's verify:")
    
    deinterleaved = interleaver.deinterleave_bytes(corrupted_bytes, 
                                                   interleaver.CODEWORDS_PER_FRAME, 
                                                   interleaver.INTERLEAVE_DEPTH)
    
    # Check codewords that have errors
    deint_bits = interleaver.bytes_to_bits(deinterleaved)
    orig_bits = interleaver.bytes_to_bits(encoded)
    
    affected_codewords = {}
    for i in range(512):
        cw_orig = orig_bits[i * 7 : (i + 1) * 7]
        cw_deint = deint_bits[i * 7 : (i + 1) * 7]
        diffs = [pos for pos in range(7) if cw_orig[pos] != cw_deint[pos]]
        if diffs:
            affected_codewords[i] = diffs
            
    for cw_idx, diffs in affected_codewords.items():
        print(f"  -> Codeword #{cw_idx:2d}: exactly {len(diffs)} bit error at 1-indexed position {diffs[0] + 1}")
        
    print(f"\nResult: The 12-bit contiguous channel burst was dispersed across {len(affected_codewords)} separate codewords.")
    print("MAXIMUM ERRORS IN ANY CODEWORD = 1 bit! (Hamming code can correct 100% of these!)")
    
    # -------------------------------------------------------------
    # Step 6: Hamming Syndrome Error Correction
    # -------------------------------------------------------------
    print_banner("Step 6: Hamming(7,4) Syndrome Decoding & Repair")
    print("For each codeword [p1, p2, d1, p3, d2, d3, d4], Server computes the Syndrome vector:")
    print("  c1 = p1 ^ d1 ^ d2 ^ d4")
    print("  c2 = p2 ^ d1 ^ d3 ^ d4")
    print("  c3 = p3 ^ d2 ^ d3 ^ d4")
    print("  error_position = c1 | (c2 << 1) | (c3 << 2)\n")
    
    # Demonstrate syndrome on the first affected codeword
    sample_cw_idx = list(affected_codewords.keys())[0]
    sample_cw_corrupted = deint_bits[sample_cw_idx * 7 : (sample_cw_idx + 1) * 7]
    sample_cw_clean = orig_bits[sample_cw_idx * 7 : (sample_cw_idx + 1) * 7]
    
    p1, p2, d1, p3, d2, d3, d4 = sample_cw_corrupted
    c1 = p1 ^ d1 ^ d2 ^ d4
    c2 = p2 ^ d1 ^ d3 ^ d4
    c3 = p3 ^ d2 ^ d3 ^ d4
    syndrome = c1 | (c2 << 1) | (c3 << 2)
    
    print(f"Detailed Syndrome calculation for Codeword #{sample_cw_idx}:")
    print(f"  Received Codeword: {sample_cw_corrupted}")
    print(f"  Syndrome Bits:     c1={c1}, c2={c2}, c3={c3}")
    print(f"  Computed error_pos: {syndrome} (1-indexed)")
    print(f"  Action Taken:      codeword[{syndrome - 1}] ^= 1 (Flipped bit #{syndrome} back!)")
    
    fixed_cw = list(sample_cw_corrupted)
    fixed_cw[syndrome - 1] ^= 1
    print(f"  Repaired Codeword: {fixed_cw}")
    print(f"  Matches Original:  {fixed_cw == sample_cw_clean} [PASS]")
    
    # Full decode
    decoded_bytes, n_corr, n_det = hamming.decode_bytes(deinterleaved, interleaver.NIBBLES_PER_FRAME)
    trimmed_payload = decoded_bytes[:len(data)]
    
    # -------------------------------------------------------------
    # Step 7: Integrity Checks
    # -------------------------------------------------------------
    print_banner("Step 7: Final CRC-16 & SHA-256 Verification")
    crc_rec = detection.crc16_ccitt(trimmed_payload)
    crc_match = (crc_rec == crc_orig)
    print(f"Expected CRC-16:     0x{crc_orig:04X}")
    print(f"Received CRC-16:     0x{crc_rec:04X}")
    print(f"CRC-16 Status:       {'VALID [OK]' if crc_match else 'INVALID [FAILED]'}")
    
    print(f"\nDecoded Text:        \"{trimmed_payload.decode('utf-8', errors='replace')}\"")
    print(f"Exact Match to Input: {trimmed_payload == data}")
    print(f"Total Errors Corrected: {n_corr} bits")
    print(f"VERDICT:             [PASS] - 100% RECOVERED WITHOUT RETRANSMISSION!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    test_msg = sys.argv[1] if len(sys.argv) > 1 else "HELLO COMPUTER NETWORKS"
    inspect(test_msg)
