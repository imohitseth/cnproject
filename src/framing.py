"""
Framing Layer for Error Detection and Correction System.

Frame format:
  [8-byte header] [encoded payload]
  
Header structure (8 bytes, Big-Endian):
  - frame_id: uint32 (4 bytes)
    - 0: metadata frame (JSON payload)
    - 1 to N: data frames
    - 0xFFFFFFFF: END sentinel frame
  - orig_len: uint16 (2 bytes) - original unpadded payload length
  - crc16: uint16 (2 bytes) - CRC-16-CCITT over raw pre-encoding payload
"""

import struct
import json
from typing import Tuple, Optional
from . import detection


# Frame constants
HEADER_SIZE = 8  # bytes
FRAME_ID_METADATA = 0
FRAME_ID_END = 0xFFFFFFFF
MAX_FRAME_ID = 0xFFFFFFFE

# Payload configuration (must match interleaver.py)
FRAME_PAYLOAD_SIZE = 256  # bytes (raw unencoded payload)
ENCODED_PAYLOAD_SIZE = 448  # bytes (after Hamming(7,4) + interleaving depth 32)


def build_metadata_frame(filename: str, filesize: int, total_frames: int, 
                         file_sha256: str) -> bytes:
    """
    Build a metadata frame (frame_id=0).
    Payload is JSON with file information.
    """
    metadata = {
        "filename": filename,
        "filesize": filesize,
        "total_frames": total_frames,
        "sha256": file_sha256
    }
    payload = json.dumps(metadata).encode('utf-8')
    orig_len = len(payload)
    if orig_len > FRAME_PAYLOAD_SIZE:
        raise ValueError(f"Metadata too large: {orig_len} > {FRAME_PAYLOAD_SIZE}")
    
    crc = detection.crc16_ccitt(payload)
    padded = payload.ljust(FRAME_PAYLOAD_SIZE, b'\x00')
    header = struct.pack('>IHH', FRAME_ID_METADATA, orig_len, crc)
    return header + padded


def build_data_frame(frame_id: int, payload: bytes) -> bytes:
    """
    Build a data frame.
    Payload is padded to FRAME_PAYLOAD_SIZE bytes for encoding & interleaving.
    Header records orig_len and CRC-16 over the unpadded payload.
    """
    if not (1 <= frame_id <= MAX_FRAME_ID):
        raise ValueError(f"frame_id must be 1-{MAX_FRAME_ID}, got {frame_id}")
    
    orig_len = len(payload)
    if orig_len > FRAME_PAYLOAD_SIZE:
        raise ValueError(f"Payload too large: {orig_len} > {FRAME_PAYLOAD_SIZE}")
    
    crc = detection.crc16_ccitt(payload)
    padded = payload.ljust(FRAME_PAYLOAD_SIZE, b'\x00')
    header = struct.pack('>IHH', frame_id, orig_len, crc)
    return header + padded


def build_end_frame() -> bytes:
    """Build an END sentinel frame (frame_id=0xFFFFFFFF)."""
    payload = b'\x00' * FRAME_PAYLOAD_SIZE
    crc = detection.crc16_ccitt(payload)
    header = struct.pack('>IHH', FRAME_ID_END, 0, crc)
    return header + payload


def parse_frame_header(header_bytes: bytes) -> Tuple[int, int, int]:
    """
    Parse an 8-byte frame header.
    Returns (frame_id, orig_len, crc16).
    """
    if len(header_bytes) != HEADER_SIZE:
        raise ValueError(f"Header must be {HEADER_SIZE} bytes, got {len(header_bytes)}")
    
    frame_id, orig_len, crc16 = struct.unpack('>IHH', header_bytes)
    return frame_id, orig_len, crc16


def parse_metadata_frame(payload: bytes) -> dict:
    """Parse metadata frame payload (JSON), stripping header if present."""
    if len(payload) >= HEADER_SIZE:
        fid, orig_len, _ = parse_frame_header(payload[:HEADER_SIZE])
        if fid == FRAME_ID_METADATA and orig_len <= len(payload) - HEADER_SIZE:
            payload = payload[HEADER_SIZE:HEADER_SIZE + orig_len]
    payload = payload.rstrip(b'\x00')
    return json.loads(payload.decode('utf-8'))


def verify_frame_crc(payload: bytes, expected_crc: int) -> bool:
    """Verify CRC-16 of a frame's payload."""
    return detection.verify_crc16(payload, expected_crc)


def framing_test():
    """Test frame building and parsing."""
    print("Running framing layer test...")
    
    # 1. Test metadata frame
    metadata = build_metadata_frame("test.txt", 1024, 5, "abc123")
    meta_id, meta_len, meta_crc = parse_frame_header(metadata[:HEADER_SIZE])
    assert meta_id == FRAME_ID_METADATA
    assert meta_len > 0
    parsed = parse_metadata_frame(metadata)
    assert parsed["filename"] == "test.txt"
    assert parsed["filesize"] == 1024
    print(f"  [PASS] Metadata frame: id={meta_id}, orig_len={meta_len}, crc=0x{meta_crc:04X}")
    
    # 2. Test data frame
    raw_content = b"Hello, World!"
    data_frame = build_data_frame(1, raw_content)
    data_id, data_len, data_crc = parse_frame_header(data_frame[:HEADER_SIZE])
    assert data_id == 1
    assert data_len == len(raw_content)
    print(f"  [PASS] Data frame: id={data_id}, orig_len={data_len}, crc=0x{data_crc:04X}")
    
    # 3. Test END frame
    end_frame = build_end_frame()
    end_id, end_len, end_crc = parse_frame_header(end_frame[:HEADER_SIZE])
    assert end_id == FRAME_ID_END
    print(f"  [PASS] END frame: id=0x{end_id:08X}")
    
    # 4. Test CRC verification
    extracted_payload = data_frame[HEADER_SIZE:HEADER_SIZE + data_len]
    assert verify_frame_crc(extracted_payload, data_crc), "Data frame CRC should match"
    print(f"  [PASS] CRC verification passed")
    
    # 5. Test CRC failure detection
    corrupted_payload = bytearray(extracted_payload)
    corrupted_payload[0] ^= 0x01
    assert not verify_frame_crc(bytes(corrupted_payload), data_crc), "Corrupted payload must fail CRC"
    print(f"  [PASS] CRC corruption detected")
    
    print("\n  [PASS] All framing tests passed!")


if __name__ == "__main__":
    framing_test()
