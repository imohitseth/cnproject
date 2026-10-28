"""
Scenario Harness - runs Client -> Relay -> Server in one process (threads).

Used by run_tests.py and demo_review.py so every scenario goes through the real
sockets, the real relay and the real server code, not a simulation.
"""

import hashlib
import os
import random
import socket
import tempfile
import threading
import time

from .server import run_tcp_server, run_udp_server
from .relay import run_tcp_relay, run_udp_relay
from .client import send_file_tcp, send_file_udp
from .framing import parse_frame_selector
from . import interleaver


def sample_content(n_bytes: int = 1229) -> bytes:
    """Deterministic readable test content (default 1229 B = 5 data frames)."""
    base = (
        "Computer Networks Final Project: Error Detection and Correction System.\n"
        "Team: Mohit Seth (24BCE2950) & Vinayak Sangram Patil (24BCE2147).\n"
        "Architecture: Client -> Relay -> Server.\n"
        "Features: Hamming(7,4) FEC, bit-level interleaving, XOR parity frames,\n"
        "CRC-16-CCITT detection and SHA-256 integrity verification.\n"
    )
    line = "Forward Error Correction allows recovery without retransmission!\n"
    text = base
    while len(text) < n_bytes:
        text += line
    return text.encode('utf-8')[:n_bytes]


def _free_port(kind: int) -> int:
    s = socket.socket(socket.AF_INET, kind)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_scenario(proto: str = 'tcp', content: bytes = None, depth: int = interleaver.INTERLEAVE_DEPTH,
                 group_size: int = 4, min_burst: int = 4, max_burst: int = 16,
                 corruption_prob: float = 1.0, target_frames: str = '', drop_frames: str = '',
                 seed: int = None, timeout: float = 30.0) -> dict:
    """
    Run one end-to-end transfer and return
      {'report': server report dict or None, 'received_equal': bool,
       'sha_ok': bool, 'original_sha256': str}
    """
    if seed is not None:
        random.seed(seed)
    content = content if content is not None else sample_content()
    kind = socket.SOCK_STREAM if proto == 'tcp' else socket.SOCK_DGRAM
    server_port, relay_port = _free_port(kind), _free_port(kind)
    targets = parse_frame_selector(target_frames) or None
    drops = parse_frame_selector(drop_frames) or None
    
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test_document.txt")
        with open(path, 'wb') as f:
            f.write(content)
        out_dir = os.path.join(tmp, "server_received")
        os.makedirs(out_dir)
        
        result = {}
        run_server = run_tcp_server if proto == 'tcp' else run_udp_server
        run_relay = run_tcp_relay if proto == 'tcp' else run_udp_relay
        send = send_file_tcp if proto == 'tcp' else send_file_udp
        
        def server_target():
            result['report'] = run_server(server_port, out_dir)
        
        server_t = threading.Thread(target=server_target, daemon=True)
        server_t.start()
        time.sleep(0.2)
        relay_t = threading.Thread(
            target=run_relay,
            args=(relay_port, server_port, corruption_prob, min_burst, max_burst, False, targets, drops),
            daemon=True)
        relay_t.start()
        time.sleep(0.2)
        
        send(path, '127.0.0.1', relay_port, depth, group_size)
        server_t.join(timeout)
        relay_t.join(2.0)
        
        received = os.path.join(out_dir, "received_test_document.txt")
        data = open(received, 'rb').read() if os.path.exists(received) else None
        report = result.get('report')
        return {
            'report': report,
            'received_equal': data == content,
            'sha_ok': bool(report and report['match']),
            'original_sha256': hashlib.sha256(content).hexdigest(),
        }
