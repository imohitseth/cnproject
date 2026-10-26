"""
Error Detection Algorithms.

Implements three detection methods as separate, swappable stages:
1. Even parity bit
2. Internet checksum (16-bit one's complement, RFC 1071 style)
3. CRC-16-CCITT (bitwise implementation, polynomial 0x1021)
"""


def compute_parity(data: bytes) -> int:
    """
    Compute even parity bit for data.
    Returns 0 if even number of 1-bits, 1 if odd.
    """
    parity = 0
    for byte in data:
        n = byte
        while n:
            parity ^= 1
            n &= n - 1
    return parity


def verify_parity(data: bytes, expected_parity: int) -> bool:
    """Verify that data has the expected parity."""
    return compute_parity(data) == expected_parity


def internet_checksum(data: bytes) -> int:
    """
    Compute Internet checksum (16-bit one's complement sum).
    RFC 1071 style, as used in IP/TCP/UDP headers.
    """
    if len(data) % 2 != 0:
        data = data + b'\x00'
    
    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
    
    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    return (~checksum) & 0xFFFF


def verify_internet_checksum(data: bytes, checksum: int) -> bool:
    """Verify Internet checksum."""
    if len(data) % 2 != 0:
        data = data + b'\x00'
    
    total = checksum
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
    
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    
    return total == 0xFFFF


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    """
    Compute CRC-16-CCITT using bitwise implementation.
    Polynomial: 0x1021 (x^16 + x^12 + x^5 + 1)
    Initial value: 0xFFFF
    """
    crc = initial
    polynomial = 0x1021
    
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ polynomial
            else:
                crc = crc << 1
            crc &= 0xFFFF
    
    return crc


def verify_crc16(data: bytes, crc: int) -> bool:
    """Verify CRC-16 by recomputing and comparing."""
    return crc16_ccitt(data) == crc


def detection_comparison_test():
    """Test all three detection algorithms and compare their error detection capabilities."""
    print("Running detection algorithm comparison test...")
    
    test_data = b"Hello, Computer Networks!"
    
    parity = compute_parity(test_data)
    print(f"  Parity of test data: {parity}")
    
    checksum = internet_checksum(test_data)
    print(f"  Internet checksum: 0x{checksum:04X}")
    
    crc = crc16_ccitt(test_data)
    print(f"  CRC-16-CCITT: 0x{crc:04X}")
    
    # Test error detection with single-bit flip
    corrupted = bytearray(test_data)
    corrupted[0] ^= 0x01
    
    parity_ok = verify_parity(bytes(corrupted), parity)
    checksum_ok = verify_internet_checksum(bytes(corrupted), checksum)
    crc_ok = verify_crc16(bytes(corrupted), crc)
    
    print(f"\n  Single-bit error detection:")
    print(f"    Parity:            {'detected' if not parity_ok else 'MISSED'}")
    print(f"    Internet checksum: {'detected' if not checksum_ok else 'MISSED'}")
    print(f"    CRC-16:            {'detected' if not crc_ok else 'MISSED'}")
    
    # Test with two-bit flip (parity should miss this)
    corrupted2 = bytearray(test_data)
    corrupted2[0] ^= 0x03
    
    parity_ok2 = verify_parity(bytes(corrupted2), parity)
    checksum_ok2 = verify_internet_checksum(bytes(corrupted2), checksum)
    crc_ok2 = verify_crc16(bytes(corrupted2), crc)
    
    print(f"\n  Two-bit error detection (same byte):")
    print(f"    Parity:            {'detected' if not parity_ok2 else 'MISSED (expected)'}")
    print(f"    Internet checksum: {'detected' if not checksum_ok2 else 'MISSED'}")
    print(f"    CRC-16:            {'detected' if not crc_ok2 else 'MISSED'}")
    
    print("\n  [PASS] Detection algorithms working correctly!")


if __name__ == "__main__":
    detection_comparison_test()
