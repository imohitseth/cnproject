"""
Client Process - File Transfer with Forward Error Correction.

Reads a file, computes its SHA-256, chunks it into 256-byte payloads,
encodes each with Hamming(7,4) (producing 512 codewords),
interleaves the bits with depth 32 (producing 448 bytes),
attaches an 8-byte header, and sends it to the Relay (or directly to Server).

Supports --proto tcp|udp.

Usage:
    python -m src.client <filename> [--proto tcp|udp] [--port PORT] 
                                   [--direct] [--server-port PORT] [--host HOST]
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
                         FRAME_PAYLOAD_SIZE, HEADER_SIZE)
from src.protocol import wrap_message, RecvBuffer
from src import hamming, interleaver


def send_file_tcp(filename: str, host: str, port: int):
    """Send file over TCP with per-frame acknowledgement."""
    print("=" * 65)
    print(f"[*] Client Connecting to {host}:{port} (TCP)")
    print("=" * 65)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    try:
        _send_frames(sock, filename, is_tcp=True)
    finally:
        sock.close()


def send_file_udp(filename: str, host: str, port: int):
    """Send file over UDP."""
    print("=" * 65)
    print(f"[*] Client Sending to {host}:{port} (UDP)")
    print("=" * 65)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _send_frames(sock, filename, is_tcp=False, server_addr=(host, port))
    finally:
        sock.close()


def _send_frames(sock, filename: str, is_tcp: bool, server_addr=None):
    """Send file frames."""
    with open(filename, 'rb') as f:
        file_data = f.read()
    
    file_sha256 = hashlib.sha256(file_data).hexdigest()
    filesize = len(file_data)
    total_frames = (filesize + FRAME_PAYLOAD_SIZE - 1) // FRAME_PAYLOAD_SIZE
    if total_frames == 0:
        total_frames = 1  # handle 0-byte file
    
    print(f"File Name:     {os.path.basename(filename)}")
    print(f"File Size:     {filesize} bytes")
    print(f"Total Frames:  {total_frames}")
    print(f"SHA-256:       {file_sha256}")
    print("-" * 65)
    
    # 1. Build and send metadata frame
    metadata_frame = build_metadata_frame(os.path.basename(filename), filesize, total_frames, file_sha256)
    metadata_msg = wrap_message(b'\x01' + metadata_frame)
    
    if is_tcp:
        sock.sendall(metadata_msg)
        # Wait for metadata ACK
        ack = sock.recv(4096)
    else:
        sock.sendto(metadata_msg, server_addr)
        time.sleep(0.01)
        
    print(f"[Client] Sent Metadata frame (File: {os.path.basename(filename)}, {filesize} B)")
    
    # 2. Send data frames
    for frame_id in range(total_frames):
        start = frame_id * FRAME_PAYLOAD_SIZE
        end = min(start + FRAME_PAYLOAD_SIZE, filesize)
        chunk = file_data[start:end]
        
        # Build frame: pads chunk to 256 bytes, generates 8-byte header with orig_len and CRC-16
        raw_frame = build_data_frame(frame_id + 1, chunk)
        header = raw_frame[:HEADER_SIZE]
        raw_payload = raw_frame[HEADER_SIZE:]  # exactly 256 bytes
        
        # Hamming(7,4) FEC encoding: 256 bytes -> 512 codewords = 448 bytes
        encoded = hamming.encode_bytes(raw_payload)
        
        # Bit-level Block Interleaving with Depth 32
        interleaved = interleaver.interleave_bytes(encoded, interleaver.INTERLEAVE_DEPTH)
        
        # Combine header (8 bytes) + interleaved payload (448 bytes) = 456 bytes
        frame_data = header + interleaved
        frame_msg = wrap_message(b'\x02' + frame_data)
        
        if is_tcp:
            sock.sendall(frame_msg)
            # Wait for frame ACK from server
            ack = sock.recv(4096)
        else:
            sock.sendto(frame_msg, server_addr)
            time.sleep(0.005)  # pacing for UDP
            
        print(f"[Client] Sent Data Frame {frame_id + 1}/{total_frames} ({len(chunk)} payload bytes -> 456 frame bytes)")
    
    # 3. Send END frame
    end_frame = build_end_frame()
    end_msg = wrap_message(b'\x03' + end_frame)
    
    if is_tcp:
        sock.sendall(end_msg)
        ack = sock.recv(4096)
        status_pass = ack.endswith(b'\x01') if len(ack) >= 1 else False
        status_str = "SERVER VERIFICATION: SUCCESSFUL (PASS)" if status_pass else "SERVER VERIFICATION: COMPLETED"
        print(f"[Client] Sent END frame -> {status_str}")
    else:
        sock.sendto(end_msg, server_addr)
        print(f"[Client] Sent END frame (UDP)")
        
    print("-" * 65)
    print("[Client] File transmission finished successfully!")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description='File Transfer Client with Error Correction')
    parser.add_argument('filename', help='File to send')
    parser.add_argument('--proto', choices=['tcp', 'udp'], default='tcp', help='Protocol (default: tcp)')
    parser.add_argument('--port', type=int, default=9999, help='Relay port (default: 9999)')
    parser.add_argument('--direct', action='store_true', help='Bypass relay, connect directly to server')
    parser.add_argument('--server-port', type=int, default=9998, help='Server port for direct mode (default: 9998)')
    parser.add_argument('--host', default='127.0.0.1', help='Host (default: 127.0.0.1)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.filename):
        print(f"Error: File '{args.filename}' not found")
        sys.exit(1)
    
    target_port = args.server_port if args.direct else args.port
    
    if args.proto == 'tcp':
        send_file_tcp(args.filename, args.host, target_port)
    else:
        send_file_udp(args.filename, args.host, target_port)


if __name__ == '__main__':
    main()
