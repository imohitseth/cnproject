"""
Relay Process - Emulated Network Layer with Diagnostic Tracing.

The relay corrupts only the encoded payload of data/parity frames. Headers,
metadata and END frames pass through intact (header kept outside the corruption
zone, as in the design).

Demo / experiment controls:
    --target-frames 3,P1   corrupt only these frames (P<n> = parity frame of group n)
    --drop-frames 2        drop these frames entirely (UDP only: models frame loss)
    --seed N               reproducible bursts
    --min-burst 40 --max-burst 40   fixed-length burst (e.g. past the depth-32 limit)

Usage:
    python -m src.relay [--port RELAY_PORT] [--server-port SERVER_PORT] 
                        [--proto tcp|udp] [--corruption-prob PROB]
                        [--min-burst MIN] [--max-burst MAX] [--verbose]
                        [--target-frames IDS] [--drop-frames IDS] [--seed N]
"""

import socket
import argparse
import random
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.channel_emulator import ChannelEmulator
from src.protocol import wrap_message, unwrap_message, RecvBuffer
from src.framing import HEADER_SIZE, parse_frame_header, frame_label, parse_frame_selector


def run_tcp_relay(relay_port: int, server_port: int, corruption_prob: float,
                  min_burst: int, max_burst: int, verbose: bool = False,
                  target_frames=None, drop_frames=None):
    """Run TCP relay with RecvBuffer framing and bidirectional forwarding."""
    print("=" * 65)
    print(f"[*] Starting TCP Relay on port {relay_port} -> Server port {server_port}")
    print(f"[*] Burst Error Settings: Prob={corruption_prob:.2f}, Range=[{min_burst}, {max_burst}] bits")
    if verbose:
        print("[*] Verbose Tracing: ENABLED (Detailed bit offsets will be logged)")
    if target_frames:
        print(f"[*] Corrupting only frames: {sorted(frame_label(i) for i in target_frames)}")
    if drop_frames:
        print("[*] --drop-frames ignored for TCP (a reliable stream cannot lose frames)")
    print("=" * 65)
    
    emulator = ChannelEmulator(
        min_burst_bits=min_burst,
        max_burst_bits=max_burst,
        corruption_probability=corruption_prob
    )
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('127.0.0.1', relay_port))
    server_sock.listen(1)
    print(f"[Relay] Listening for client on 127.0.0.1:{relay_port}...")
    
    client_conn, client_addr = server_sock.accept()
    print(f"[Relay] Client connected from {client_addr}")
    
    server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_conn.connect(('127.0.0.1', server_port))
    print(f"[Relay] Connected to Server on 127.0.0.1:{server_port}")
    
    client_buffer = RecvBuffer()
    
    try:
        while True:
            data = client_conn.recv(4096)
            if not data:
                print("[Relay] Client closed connection")
                break
                
            client_buffer.add_data(data)
            messages = client_buffer.pop_all_messages()
            
            for message in messages:
                if len(message) < 1:
                    continue
                
                msg_type = message[0]
                frame_data = message[1:]
                
                if msg_type == 2 and len(frame_data) > HEADER_SIZE:
                    header = frame_data[:HEADER_SIZE]
                    payload = frame_data[HEADER_SIZE:]
                    
                    frame_id, orig_len, _ = parse_frame_header(header)
                    label = frame_label(frame_id)
                    if target_frames and frame_id not in target_frames:
                        corrupted_payload, n_flipped = payload, 0
                    else:
                        corrupted_payload, n_flipped = emulator.corrupt_burst(payload)
                    frame_data = header + corrupted_payload
                    
                    if n_flipped > 0:
                        info = emulator.last_burst_info
                        print(f"  [Relay] Frame {label}: INJECTED burst error ({n_flipped} bits flipped)")
                        if verbose:
                            print(f"          -> Channel Bit Offset: {info['start_bit']} (Byte {info['byte_index']}, bit {info['bit_in_byte']})")
                            print(f"          -> Bit Range Corrupted: [{info['start_bit']} .. {info['start_bit'] + n_flipped - 1}]")
                    else:
                        print(f"  [Relay] Frame {label}: Transmitted cleanly (no corruption)")
                elif msg_type == 1:
                    print("  [Relay] Metadata frame received -> Forwarding intact")
                elif msg_type == 3:
                    print("  [Relay] END frame received -> Forwarding intact")
                    
                # Forward to server
                server_conn.sendall(wrap_message(bytes([msg_type]) + frame_data))
                
                # Forward server response to client
                resp_data = server_conn.recv(4096)
                if resp_data:
                    client_conn.sendall(resp_data)
                    
    finally:
        client_conn.close()
        server_conn.close()
        server_sock.close()
        emulator.print_stats()


def run_udp_relay(relay_port: int, server_port: int, corruption_prob: float,
                  min_burst: int, max_burst: int, verbose: bool = False,
                  target_frames=None, drop_frames=None):
    """Run UDP relay forwarding packets with burst corruption."""
    print("=" * 65)
    print(f"[*] Starting UDP Relay on port {relay_port} -> Server port {server_port}")
    print(f"[*] Burst Error Settings: Prob={corruption_prob:.2f}, Range=[{min_burst}, {max_burst}] bits")
    if target_frames:
        print(f"[*] Corrupting only frames: {sorted(frame_label(i) for i in target_frames)}")
    if drop_frames:
        print(f"[*] Dropping frames: {sorted(frame_label(i) for i in drop_frames)}")
    print("=" * 65)
    
    emulator = ChannelEmulator(
        min_burst_bits=min_burst,
        max_burst_bits=max_burst,
        corruption_probability=corruption_prob
    )
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', relay_port))
    print(f"[Relay] Listening on 127.0.0.1:{relay_port} (UDP)...")
    
    server_addr = ('127.0.0.1', server_port)
    
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
            
            if msg_type == 2 and len(frame_data) > HEADER_SIZE:
                header = frame_data[:HEADER_SIZE]
                payload = frame_data[HEADER_SIZE:]
                frame_id, orig_len, _ = parse_frame_header(header)
                label = frame_label(frame_id)
                if drop_frames and frame_id in drop_frames:
                    print(f"  [Relay] UDP Frame {label}: DROPPED (frame loss)")
                    continue
                if target_frames and frame_id not in target_frames:
                    corrupted_payload, n_flipped = payload, 0
                else:
                    corrupted_payload, n_flipped = emulator.corrupt_burst(payload)
                frame_data = header + corrupted_payload
                if n_flipped > 0:
                    info = emulator.last_burst_info
                    print(f"  [Relay] UDP Frame {label}: INJECTED burst error ({n_flipped} bits flipped)")
                    if verbose:
                        print(f"          -> Channel Bit Offset: {info['start_bit']} (Byte {info['byte_index']}, bit {info['bit_in_byte']})")
                else:
                    print(f"  [Relay] UDP Frame {label}: Transmitted cleanly")
            elif msg_type == 1:
                print("  [Relay] UDP Metadata frame received -> Forwarding intact")
            elif msg_type == 3:
                print("  [Relay] UDP END frame received -> Forwarding intact")
                
            sock.sendto(wrap_message(bytes([msg_type]) + frame_data), server_addr)
            
            if msg_type == 3:
                break
                
    finally:
        sock.close()
        emulator.print_stats()


def main():
    parser = argparse.ArgumentParser(description='Network Relay with Burst Error Emulation')
    parser.add_argument('--port', type=int, default=9999, help='Relay port (default: 9999)')
    parser.add_argument('--server-port', type=int, default=9998, help='Server port (default: 9998)')
    parser.add_argument('--proto', choices=['tcp', 'udp'], default='tcp', help='Protocol (default: tcp)')
    parser.add_argument('--corruption-prob', type=float, default=0.5, 
                        help='Corruption probability 0.0-1.0 (default: 0.5)')
    parser.add_argument('--min-burst', type=int, default=1, 
                        help='Minimum burst bits (default: 1)')
    parser.add_argument('--max-burst', type=int, default=16, 
                        help='Maximum burst bits (default: 16; Hamming+interleave alone corrects up to 32)')
    parser.add_argument('--target-frames', default='',
                        help='Corrupt only these frames, e.g. "3" or "2,P1" (P<n> = parity frame of group n)')
    parser.add_argument('--drop-frames', default='',
                        help='Drop these frames entirely (UDP only), e.g. "2"')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for reproducible bursts')
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='Enable verbose bit-offset logging')
    
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    targets = parse_frame_selector(args.target_frames) or None
    drops = parse_frame_selector(args.drop_frames) or None
    
    if args.proto == 'tcp':
        run_tcp_relay(args.port, args.server_port, args.corruption_prob, 
                      args.min_burst, args.max_burst, args.verbose, targets, drops)
    else:
        run_udp_relay(args.port, args.server_port, args.corruption_prob,
                      args.min_burst, args.max_burst, args.verbose, targets, drops)


if __name__ == '__main__':
    main()
