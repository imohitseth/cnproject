"""
Channel Emulator - Burst Error Injection.

Corrupts a contiguous run of bits (not whole random bytes with multi-bit
flips within one byte). Picks a random start bit and a random burst length
(in bits) within a configurable range, then flips exactly those bits.

Tracks statistics: frames seen, frames corrupted, bits flipped.
"""

import random
from typing import Tuple, Dict, Any


class ChannelEmulator:
    """Emulates a noisy communication channel with burst errors."""
    
    def __init__(self, min_burst_bits: int = 1, max_burst_bits: int = 16,
                 corruption_probability: float = 0.5):
        self.min_burst_bits = min_burst_bits
        self.max_burst_bits = max_burst_bits
        self.corruption_probability = corruption_probability
        
        self.frames_seen = 0
        self.frames_corrupted = 0
        self.total_bits_flipped = 0
        self.last_burst_info: Dict[str, Any] = {}
    
    def corrupt_burst(self, data: bytes) -> Tuple[bytes, int]:
        """Inject a burst of bit errors into data."""
        self.frames_seen += 1
        self.last_burst_info = {
            'corrupted': False,
            'start_bit': -1,
            'length': 0,
            'byte_index': -1,
            'bit_in_byte': -1
        }
        
        if random.random() > self.corruption_probability:
            return data, 0
        
        # Convert to bit array
        bits = bytearray(len(data) * 8)
        for i, byte in enumerate(data):
            for j in range(8):
                bits[i * 8 + j] = (byte >> (7 - j)) & 1
        
        total_bits = len(bits)
        burst_length = random.randint(self.min_burst_bits, 
                                      min(self.max_burst_bits, total_bits))
        start_bit = random.randint(0, total_bits - burst_length)
        
        for i in range(burst_length):
            bits[start_bit + i] ^= 1
        
        corrupted = bytearray(len(data))
        for i in range(len(data)):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[i * 8 + j]
            corrupted[i] = byte
        
        self.frames_corrupted += 1
        self.total_bits_flipped += burst_length
        self.last_burst_info = {
            'corrupted': True,
            'start_bit': start_bit,
            'length': burst_length,
            'byte_index': start_bit // 8,
            'bit_in_byte': 7 - (start_bit % 8)
        }
        
        return bytes(corrupted), burst_length
    
    def get_stats(self) -> dict:
        return {
            "frames_seen": self.frames_seen,
            "frames_corrupted": self.frames_corrupted,
            "total_bits_flipped": self.total_bits_flipped,
            "corruption_rate": self.frames_corrupted / max(1, self.frames_seen)
        }
    
    def print_stats(self):
        stats = self.get_stats()
        print("\n" + "=" * 60)
        print("Channel Emulator Statistics")
        print("=" * 60)
        print(f"  Frames seen:        {stats['frames_seen']}")
        print(f"  Frames corrupted:   {stats['frames_corrupted']}")
        print(f"  Total bits flipped: {stats['total_bits_flipped']}")
        print(f"  Corruption rate:    {stats['corruption_rate']:.1%}")
        print("=" * 60)


def channel_emulator_test():
    print("Running channel emulator test...")
    emulator = ChannelEmulator(min_burst_bits=8, max_burst_bits=48, 
                               corruption_probability=1.0)
    test_data = b'\x00' * 100
    corrupted, n_flipped = emulator.corrupt_burst(test_data)
    
    diff_bits = 0
    for i in range(len(test_data) * 8):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)
        orig_bit = (test_data[byte_idx] >> bit_idx) & 1
        corr_bit = (corrupted[byte_idx] >> bit_idx) & 1
        if orig_bit != corr_bit:
            diff_bits += 1
    
    print(f"  Burst length: {n_flipped} bits")
    print(f"  Actual flipped: {diff_bits} bits")
    
    stats = emulator.get_stats()
    if n_flipped == diff_bits and stats['frames_corrupted'] == 1:
        print("  [PASS] Channel emulator test passed!")
    else:
        print("  [FAIL] Channel emulator test failed!")


if __name__ == "__main__":
    channel_emulator_test()
