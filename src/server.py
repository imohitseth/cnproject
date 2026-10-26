"""
Server Process - File Reception with Error Correction and Integrity Verification.

Usage:
    python -m src.server [--proto tcp|udp] [--port PORT] [--output-dir DIR] [--verbose]
"""

import socket
import argparse
import sys
import os
import hashlib
import struct

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.framing import (parse_frame_header, parse_metadata_frame, verify_frame_crc,
                         FRAME_PAYLOAD_SIZE, HEADER_SIZE, FRAME_ID_METADATA, FRAME_ID_END)
from src.protocol import wrap_message, unwrap_message, RecvBuffer
from src import hamming, interleaver, detection


class FileReceiver:
    """Receives, error-corrects, and reassembles file from frames."""
    
    def __init__(self, output_dir: str = '.', verbose: bool = False):
        self.output_dir = output_dir
        self.verbose = verbose
        self.metadata = None
        self.frames = {}
        self.total_frames = 0
        self.received_frames = 0
        
        # Statistics
        self.total_errors_corrected = 0
        self.frames_crc_passed = 0
        self.frames_crc_failed = 0
        self.frame_stats = []
    
    def process_metadata(self, frame_data: bytes):
        """Process metadata frame."""
        self.metadata = parse_metadata_frame(frame_data)
        self.total_frames = self.metadata['total_frames']
        print("-" * 65)
        print(f"[Server] Metadata Received:")
        print(f"  Filename:     {self.metadata['filename']}")
        print(f"  Filesize:     {self.metadata['filesize']} bytes")
        print(f"  Total frames: {self.total_frames}")
        print(f"  SHA-256:      {self.metadata['sha256']}")
        print("-" * 65)
    
    def process_data_frame(self, frame_id: int, frame_data: bytes):
        """Process a data frame through de-interleaving and Hamming decoding."""
        header = frame_data[:HEADER_SIZE]
        encoded_payload = frame_data[HEADER_SIZE:]
        
        fid, orig_len, expected_crc = parse_frame_header(header)
        
        # Step 1: Bit-level block de-interleaving (depth 32)
        deinterleaved = interleaver.deinterleave_bytes(
            encoded_payload, 
            interleaver.CODEWORDS_PER_FRAME, 
            interleaver.INTERLEAVE_DEPTH
        )
        
        # Step 2: Hamming(7,4) decoding with syndrome error correction
        raw_payload, n_corrected, n_detected, repair_details = hamming.decode_bytes(
            deinterleaved, 
            interleaver.NIBBLES_PER_FRAME,
            return_details=True
        )
        
        # Step 3: Trim to original payload length
        raw_payload = raw_payload[:orig_len]
        
        # Step 4: CRC-16 verification
        crc_ok = verify_frame_crc(raw_payload, expected_crc)
        
        # Store frame
        self.frames[frame_id] = raw_payload
        self.received_frames += 1
        self.total_errors_corrected += n_corrected
        
        if crc_ok:
            self.frames_crc_passed += 1
            status_str = "CRC-16: VALID [OK]"
        else:
            self.frames_crc_failed += 1
            status_str = "CRC-16: INVALID [FAIL]"
            
        corr_info = f"({n_corrected} bit errors corrected)" if n_corrected > 0 else "(clean)"
        print(f"  [Server] Frame #{frame_id:2d}: {status_str} {corr_info}")
        
        if self.verbose and repair_details:
            details_str = ", ".join([f"CW#{cw} bit {pos}" for cw, pos in repair_details[:8]])
            if len(repair_details) > 8:
                details_str += f", ... +{len(repair_details) - 8} more"
            print(f"          -> Repaired Syndromes: [{details_str}]")
        
        self.frame_stats.append({
            'frame_id': frame_id,
            'errors_corrected': n_corrected,
            'crc_ok': crc_ok
        })
    
    def finalize(self) -> bool:
        """Reassemble file and verify end-to-end integrity via SHA-256."""
        if not self.metadata:
            print("[Server] Error: No metadata received before finalize.")
            return False
            
        print("-" * 65)
        print(f"[Server] Reassembling {self.received_frames}/{self.total_frames} frames...")
        
        file_data = bytearray()
        for frame_id in range(1, self.total_frames + 1):
            if frame_id in self.frames:
                file_data.extend(self.frames[frame_id])
            else:
                print(f"  [Server] Warning: Missing frame #{frame_id}!")
                file_data.extend(b'\x00' * FRAME_PAYLOAD_SIZE)
        
        final_bytes = bytes(file_data[:self.metadata['filesize']])
        out_name = f"received_{self.metadata['filename']}"
        output_path = os.path.join(self.output_dir, out_name)
        with open(output_path, 'wb') as f:
            f.write(final_bytes)
            
        received_sha256 = hashlib.sha256(final_bytes).hexdigest()
        expected_sha256 = self.metadata['sha256']
        match = (received_sha256 == expected_sha256)
        
        print("\n" + "=" * 65)
        print("          END-TO-END TRANSFER & VERIFICATION REPORT          ")
        print("=" * 65)
        print(f"  Target File:            {self.metadata['filename']}")
        print(f"  Saved To:               {output_path}")
        print(f"  Original Size:          {self.metadata['filesize']} bytes")
        print(f"  Total Frames Received:  {self.received_frames} / {self.total_frames}")
        print(f"  Bit Errors Corrected:   {self.total_errors_corrected}")
        print(f"  Frames with CRC PASS:   {self.frames_crc_passed}")
        print(f"  Frames with CRC FAIL:   {self.frames_crc_failed}")
        print(f"  Expected SHA-256:       {expected_sha256}")
        print(f"  Received SHA-256:       {received_sha256}")
        print("-" * 65)
        if match:
            print("  VERDICT: [PASS] - FILE INTEGRITY 100% VERIFIED!")
            print("  Forward Error Correction successfully restored all data without retransmission.")
        else:
            print("  VERDICT: [FAIL] - HASH MISMATCH DETECTED!")
        print("=" * 65 + "\n")
        
        return match


def run_tcp_server(port: int, output_dir: str, verbose: bool = False):
    """Run TCP server with streaming RecvBuffer."""
    print("=" * 65)
    print(f"[*] Starting TCP Server on port {port}...")
    if verbose:
        print("[*] Verbose Tracing: ENABLED (Detailed syndrome repairs will be logged)")
    print("=" * 65)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    sock.listen(1)
    print(f"[Server] Listening on 127.0.0.1:{port} (TCP)...")
    
    conn, addr = sock.accept()
    print(f"[Server] Connected by {addr}")
    
    receiver = FileReceiver(output_dir, verbose=verbose)
    recv_buffer = RecvBuffer()
    
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
                
            recv_buffer.add_data(data)
            messages = recv_buffer.pop_all_messages()
            
            for message in messages:
                if len(message) < 1:
                    continue
                
                msg_type = message[0]
                frame_data = message[1:]
                
                if msg_type == 1:
                    receiver.process_metadata(frame_data)
                    conn.sendall(wrap_message(b'\x10'))
                elif msg_type == 2:
                    header = frame_data[:8]
                    frame_id, _, _ = parse_frame_header(header)
                    receiver.process_data_frame(frame_id, frame_data)
                    conn.sendall(wrap_message(b'\x11'))
                elif msg_type == 3:
                    match = receiver.finalize()
                    conn.sendall(wrap_message(b'\x12' + (b'\x01' if match else b'\x00')))
                    return
    finally:
        conn.close()
        sock.close()


def run_udp_server(port: int, output_dir: str, verbose: bool = False):
    """Run UDP server."""
    print("=" * 65)
    print(f"[*] Starting UDP Server on port {port}...")
    if verbose:
        print("[*] Verbose Tracing: ENABLED")
    print("=" * 65)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', port))
    print(f"[Server] Listening on 127.0.0.1:{port} (UDP)...")
    
    receiver = FileReceiver(output_dir, verbose=verbose)
    
    try:
        while True:
            data, addr = sock.recvfrom(65535)
            try:
                message = unwrap_message(data)
            except ValueError:
                continue
                
            if len(message) < 1:
                continue
                
            msg_type = message[0]
            frame_data = message[1:]
            
            if msg_type == 1:
                receiver.process_metadata(frame_data)
                sock.sendto(wrap_message(b'\x10'), addr)
            elif msg_type == 2:
                header = frame_data[:8]
                frame_id, _, _ = parse_frame_header(header)
                receiver.process_data_frame(frame_id, frame_data)
                sock.sendto(wrap_message(b'\x11'), addr)
            elif msg_type == 3:
                match = receiver.finalize()
                sock.sendto(wrap_message(b'\x12' + (b'\x01' if match else b'\x00')), addr)
                return
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description='File Transfer Server with Error Correction')
    parser.add_argument('--proto', choices=['tcp', 'udp'], default='tcp', help='Protocol (default: tcp)')
    parser.add_argument('--port', type=int, default=9998, help='Server port (default: 9998)')
    parser.add_argument('--output-dir', default='.', help='Output directory (default: current)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose syndrome repair logging')
    
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    
    if args.proto == 'tcp':
        run_tcp_server(args.port, args.output_dir, verbose=args.verbose)
    else:
        run_udp_server(args.port, args.output_dir, verbose=args.verbose)


if __name__ == '__main__':
    main()
