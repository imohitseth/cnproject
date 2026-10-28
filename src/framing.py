"""
Framing Layer for Error Detection and Correction System.

Frame format:
  [8-byte header] [encoded payload]
  
Header structure (8 bytes, Big-Endian):
  - frame_id: uint32 (4 bytes)
    - 0: metadata frame (JSON payload)
    - 1 to N: data frames
    - 0x80000000 | g: XOR parity frame of group g (g = 0, 1, 2, ...)
    - 0xFFFFFFFF: END sentinel frame
  - orig_len: uint16 (2 bytes) - original unpadded payload length
  - crc16: uint16 (2 bytes) - CRC-16-CCITT over raw pre-encoding payload

Outer layer (XOR parity):
  Data frames are grouped in sets of k (default 4). After each group the client
  sends one parity frame whose raw payload is the byte-wise XOR of the group's
  256-byte padded payloads. A parity frame has the same 456-byte layout as a
  data frame, so the relay, interleaver and Hamming code treat it identically.
  Group of data frame f (1-based): (f - 1) // k.
"""

import struct
import json
from typing import Tuple, Optional
from . import detection


# Frame constants
HEADER_SIZE = 8  # bytes
FRAME_ID_METADATA = 0
FRAME_ID_END = 0xFFFFFFFF
PARITY_FLAG = 0x80000000          # high bit set => parity frame
MAX_DATA_FRAME_ID = 0x7FFFFFFF    # data frame ids must leave the high bit clear
MAX_FRAME_ID = MAX_DATA_FRAME_ID  # backward-compatible alias
DEFAULT_GROUP_SIZE = 4            # data frames per parity frame (0 disables parity)

# Payload configuration (must match interleaver.py)
FRAME_PAYLOAD_SIZE = 256  # bytes (raw unencoded payload)
ENCODED_PAYLOAD_SIZE = 448  # bytes (after Hamming(7,4) + interleaving depth 32)


def build_metadata_frame(filename: str, filesize: int, total_frames: int, 
                         file_sha256: str, depth: int = 32,
                         group_size: int = DEFAULT_GROUP_SIZE) -> bytes:
    """
    Build a metadata frame (frame_id=0).
    Payload is JSON with file information plus the protection settings the
    receiver needs (interleave depth, parity group size).
    """
    metadata = {
        "filename": filename,
        "filesize": filesize,
        "total_frames": total_frames,
        "sha256": file_sha256,
        "depth": depth,
        "group_size": group_size
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
    if not (1 <= frame_id <= MAX_DATA_FRAME_ID):
        raise ValueError(f"frame_id must be 1-{MAX_DATA_FRAME_ID}, got {frame_id}")
    
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


def build_parity_frame(group_index: int, parity_payload: bytes) -> bytes:
    """
    Build the XOR parity frame for group `group_index` (0-based).
    `parity_payload` is the 256-byte XOR of the group's padded payloads.
    """
    if len(parity_payload) != FRAME_PAYLOAD_SIZE:
        raise ValueError(f"Parity payload must be {FRAME_PAYLOAD_SIZE} bytes, got {len(parity_payload)}")
    if not (0 <= group_index < PARITY_FLAG - 1):
        raise ValueError(f"Invalid group index {group_index}")
    crc = detection.crc16_ccitt(parity_payload)
    header = struct.pack('>IHH', parity_frame_id(group_index), FRAME_PAYLOAD_SIZE, crc)
    return header + parity_payload


def parity_frame_id(group_index: int) -> int:
    """frame_id used by the parity frame of group `group_index` (0-based)."""
    return PARITY_FLAG | group_index


def is_parity_frame_id(frame_id: int) -> bool:
    """True for parity frames (high bit set), excluding the END sentinel."""
    return bool(frame_id & PARITY_FLAG) and frame_id != FRAME_ID_END


def parity_group_index(frame_id: int) -> int:
    """Group index (0-based) a parity frame protects."""
    return frame_id & ~PARITY_FLAG


def group_of(frame_id: int, group_size: int) -> int:
    """Group index (0-based) of data frame `frame_id` (1-based)."""
    return (frame_id - 1) // group_size


def group_frame_ids(group_index: int, group_size: int, total_frames: int) -> list:
    """Data frame ids (1-based) in a group; the last group may be shorter."""
    first = group_index * group_size + 1
    last = min(first + group_size - 1, total_frames)
    return list(range(first, last + 1))


def frame_label(frame_id: int) -> str:
    """Human-readable label: '#3' for data frames, 'P1' for the first parity frame."""
    if is_parity_frame_id(frame_id):
        return f"P{parity_group_index(frame_id) + 1}"
    return f"#{frame_id}"


def parse_frame_selector(spec: str) -> set:
    """
    Parse a comma-separated frame list such as "3,P1" into frame ids.
    Plain numbers are data frames; P<n> is the parity frame of group n (1-based).
    """
    ids = set()
    for token in (spec or "").split(','):
        token = token.strip().upper()
        if not token:
            continue
        if token.startswith('P'):
            ids.add(parity_frame_id(int(token[1:]) - 1))
        else:
            ids.add(int(token))
    return ids


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
    
    # 6. Test parity frame ids and grouping
    pf = build_parity_frame(1, bytes(range(256)))
    pid, plen, pcrc = parse_frame_header(pf[:HEADER_SIZE])
    assert len(pf) == HEADER_SIZE + FRAME_PAYLOAD_SIZE and plen == FRAME_PAYLOAD_SIZE
    assert is_parity_frame_id(pid) and parity_group_index(pid) == 1
    assert not is_parity_frame_id(5) and not is_parity_frame_id(FRAME_ID_END)
    assert group_of(1, 4) == 0 and group_of(4, 4) == 0 and group_of(5, 4) == 1
    assert group_frame_ids(1, 4, 6) == [5, 6]
    assert parse_frame_selector("3,P1") == {3, parity_frame_id(0)}
    print(f"  [PASS] Parity frame id/group helpers: id=0x{pid:08X}, label={frame_label(pid)}")
    
    print("\n  [PASS] All framing tests passed!")


if __name__ == "__main__":
    framing_test()
