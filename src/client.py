"""
Client Process - File Transfer with Forward Error Correction.

Reads a file, computes its SHA-256, chunks it into 256-byte payloads and protects
every payload in three steps:

  1. Hamming(7,4) encoding           256 B -> 512 codewords = 448 B
  2. Bit-level block interleaving    depth D (default 32) codewords per block
  3. 8-byte header (frame_id, orig_len, CRC-16 of the raw payload)

After every group of k data frames (default 4) it also sends one XOR parity
frame (outer layer) so the receiver can rebuild a frame that a long burst
destroyed. The parity frame goes through the same Hamming + interleaving path.

Supports --proto tcp|udp.

Usage:
    python -m src.client <filename> [--proto tcp|udp] [--port PORT]
                         [--direct] [--server-port PORT] [--host HOST]
                         [--depth 8|16|32|64|128|256|512] [--group-size K]
"""

import socket
import argparse
import sys
import os
import time
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.framing import (build_metadata_frame, build_data_frame, build_end_frame,
                         build_parity_frame, parity_frame_id, frame_label,
                         FRAME_PAYLOAD_SIZE, HEADER_SIZE, DEFAULT_GROUP_SIZE)
from src.protocol import wrap_message
from src import hamming, interleaver, parity


def send_file_tcp(filename: str, host: str, port: int,
                  depth: int = interleaver.INTERLEAVE_DEPTH,
                  group_size: int = DEFAULT_GROUP_SIZE):
    """Send file over TCP (the per-frame reply is flow control, never a retransmission request)."""
    print("=" * 65)
    print(f"[*] Client Connecting to {host}:{port} (TCP)")
    print("=" * 65)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    try:
        _send_frames(sock, filename, is_tcp=True, depth=depth, group_size=group_size)
    finally:
        sock.close()


def send_file_udp(filename: str, host: str, port: int,
                  depth: int = interleaver.INTERLEAVE_DEPTH,
                  group_size: int = DEFAULT_GROUP_SIZE):
    """Send file over UDP."""
    print("=" * 65)
    print(f"[*] Client Sending to {host}:{port} (UDP)")
    print("=" * 65)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _send_frames(sock, filename, is_tcp=False, server_addr=(host, port),
                     depth=depth, group_size=group_size)
    finally:
        sock.close()


def encode_frame(header: bytes, raw_payload: bytes, depth: int) -> bytes:
    """Hamming-encode and interleave a 256-byte raw payload; prepend the 8-byte header."""
    encoded = hamming.encode_bytes(raw_payload)                      # 256 B -> 448 B
    interleaved = interleaver.interleave_bytes(encoded, depth)       # bit-level, depth D
    return header + interleaved                                      # 8 + 448 = 456 B


def _transmit(sock, msg: bytes, is_tcp: bool, server_addr):
    """Send one wrapped message; TCP waits for the server's flow-control ack."""
    if is_tcp:
        sock.sendall(msg)
        return sock.recv(4096)
    sock.sendto(msg, server_addr)
    time.sleep(0.005)  # pacing for UDP
    return b''


def _send_frames(sock, filename: str, is_tcp: bool, server_addr=None,
                 depth: int = interleaver.INTERLEAVE_DEPTH,
                 group_size: int = DEFAULT_GROUP_SIZE):
    """Send metadata, data frames, parity frames and the END frame."""
    interleaver.validate_depth(depth)
    if group_size < 0:
        raise ValueError("group_size must be >= 0 (0 disables parity)")
    
    with open(filename, 'rb') as f:
        file_data = f.read()
    
    file_sha256 = hashlib.sha256(file_data).hexdigest()
    filesize = len(file_data)
    total_frames = (filesize + FRAME_PAYLOAD_SIZE - 1) // FRAME_PAYLOAD_SIZE
    if total_frames == 0:
        total_frames = 1  # handle 0-byte file
    n_parity = (total_frames + group_size - 1) // group_size if group_size > 0 else 0
    
    print(f"File Name:     {os.path.basename(filename)}")
    print(f"File Size:     {filesize} bytes")
    print(f"Total Frames:  {total_frames} data + {n_parity} parity")
    print(f"Protection:    Hamming(7,4) + interleave depth {depth}"
          + (f" + XOR parity (1 per {group_size} frames)" if group_size else " (parity OFF)"))
    print(f"SHA-256:       {file_sha256}")
    print("-" * 65)
    
    # 1. Metadata frame (carries depth and group size to the receiver)
    metadata_frame = build_metadata_frame(os.path.basename(filename), filesize, total_frames,
                                          file_sha256, depth=depth, group_size=group_size)
    _transmit(sock, wrap_message(b'\x01' + metadata_frame), is_tcp, server_addr)
    if not is_tcp:
        time.sleep(0.01)
    print(f"[Client] Sent Metadata frame (File: {os.path.basename(filename)}, {filesize} B)")
    
    # 2. Data frames, and a parity frame after each group
    group_payloads = []
    for idx in range(total_frames):
        frame_id = idx + 1
        start = idx * FRAME_PAYLOAD_SIZE
        end = min(start + FRAME_PAYLOAD_SIZE, filesize)
        chunk = file_data[start:end]
        
        raw_frame = build_data_frame(frame_id, chunk)   # pads to 256 B, header has orig_len + CRC-16
        header = raw_frame[:HEADER_SIZE]
        raw_payload = raw_frame[HEADER_SIZE:]           # exactly 256 bytes
        
        frame_data = encode_frame(header, raw_payload, depth)
        _transmit(sock, wrap_message(b'\x02' + frame_data), is_tcp, server_addr)
        print(f"[Client] Sent Data Frame {frame_id}/{total_frames} "
              f"({len(chunk)} payload bytes -> {len(frame_data)} frame bytes)")
        
        if group_size > 0:
            group_payloads.append(raw_payload)
            if len(group_payloads) == group_size or frame_id == total_frames:
                g = idx // group_size
                parity_payload = parity.build_parity_payload(group_payloads)
                parity_frame = build_parity_frame(g, parity_payload)
                p_data = encode_frame(parity_frame[:HEADER_SIZE], parity_frame[HEADER_SIZE:], depth)
                _transmit(sock, wrap_message(b'\x02' + p_data), is_tcp, server_addr)
                print(f"[Client] Sent Parity Frame {frame_label(parity_frame_id(g))} "
                      f"(XOR of {len(group_payloads)} data frame(s) -> {len(p_data)} frame bytes)")
                group_payloads = []
    
    # 3. END frame
    ack = _transmit(sock, wrap_message(b'\x03' + build_end_frame()), is_tcp, server_addr)
    if is_tcp:
        status_pass = ack.endswith(b'\x01') if len(ack) >= 1 else False
        status_str = ("SERVER VERIFICATION: SUCCESSFUL (PASS)" if status_pass
                      else "SERVER VERIFICATION: FAILED (hash mismatch reported)")
        print(f"[Client] Sent END frame -> {status_str}")
    else:
        print(f"[Client] Sent END frame (UDP)")
        
    print("-" * 65)
    print("[Client] File transmission finished (no retransmissions were sent).")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description='File Transfer Client with Error Correction')
    parser.add_argument('filename', help='File to send')
    parser.add_argument('--proto', choices=['tcp', 'udp'], default='tcp', help='Protocol (default: tcp)')
    parser.add_argument('--port', type=int, default=9999, help='Relay port (default: 9999)')
    parser.add_argument('--direct', action='store_true', help='Bypass relay, connect directly to server')
    parser.add_argument('--server-port', type=int, default=9998, help='Server port for direct mode (default: 9998)')
    parser.add_argument('--host', default='127.0.0.1', help='Host (default: 127.0.0.1)')
    parser.add_argument('--depth', type=int, default=interleaver.INTERLEAVE_DEPTH,
                        choices=interleaver.VALID_DEPTHS,
                        help='Interleave depth in codewords (default: 32)')
    parser.add_argument('--group-size', type=int, default=DEFAULT_GROUP_SIZE,
                        help='Data frames per XOR parity frame (default: 4, 0 disables parity)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.filename):
        print(f"Error: File '{args.filename}' not found")
        sys.exit(1)
    
    target_port = args.server_port if args.direct else args.port
    
    if args.proto == 'tcp':
        send_file_tcp(args.filename, args.host, target_port, args.depth, args.group_size)
    else:
        send_file_udp(args.filename, args.host, target_port, args.depth, args.group_size)


if __name__ == '__main__':
    main()
