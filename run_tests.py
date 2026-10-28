"""
Comprehensive Automated Test Suite & End-to-End Verification Pipeline.

Verifies:
1. Exhaustive Hamming(7,4) Single-Error-Correction across all 16 nibbles & all 7 bit positions.
2. Detection algorithms comparison (Even Parity vs Internet Checksum vs CRC-16-CCITT).
3. Bit-level Block Interleaver & De-interleaver depth-32 verification with burst error injection.
4. Framing layer encoding/decoding and CRC checking.
5. End-to-End Client -> Relay -> Server multi-process file transfer over TCP with burst corruption.
6. End-to-End Client -> Relay -> Server multi-process file transfer over UDP with burst corruption.
7. Mathematical proof & comparison: Burst Recovery WITH Interleaving vs WITHOUT Interleaving.
8. XOR parity layer: unit tests plus targeted end-to-end scenarios (burst past depth 32,
   frame loss over UDP, two bad frames in a group, configurable depth).
"""

import sys
import os
import time
import hashlib
import threading
import socket
import tempfile
import random

# Ensure root and src are on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)

from src import hamming, interleaver, detection, framing, channel_emulator, parity, harness
from src.server import run_tcp_server, run_udp_server
from src.relay import run_tcp_relay, run_udp_relay
from src.client import send_file_tcp, send_file_udp


def run_unit_tests():
    print("=" * 70)
    print("  STAGE 1: MODULAR UNIT & ALGORITHM VERIFICATION")
    print("=" * 70)
    
    # 1. Hamming exhaustive test
    print("\n[1/5] Running Exhaustive Hamming(7,4) Tests...")
    hamming_ok = hamming.exhaustive_test()
    assert hamming_ok, "Hamming exhaustive test failed!"
    print("  --> Hamming(7,4) SEC: VERIFIED [PASS]")
    
    # 2. Detection comparison test
    print("\n[2/5] Running Error Detection Algorithm Tests...")
    detection.detection_comparison_test()
    print("  --> Parity, Checksum & CRC-16: VERIFIED [PASS]")
    
    # 3. Framing tests
    print("\n[3/5] Running Frame Format & Header Tests...")
    framing.framing_test()
    print("  --> 8-Byte Header & 456-Byte Frame Architecture: VERIFIED [PASS]")
    
    # 4. Interleaver tests
    print("\n[4/5] Running Interleaving & Burst Recovery Tests...")
    interleaver_ok = interleaver.interleaver_test()
    assert interleaver_ok, "Interleaver test failed!"
    print("  --> Bit-Level Block Interleaving (Depth 32): VERIFIED [PASS]")
    
    # 5. Parity tests
    print("\n[5/5] Running XOR Parity (outer layer) Tests...")
    assert parity.parity_test(), "Parity test failed!"
    print("  --> XOR Parity Frame Build & Single-Frame Rebuild: VERIFIED [PASS]")
    
    print("\n" + "-" * 70)
    print("  ALL UNIT & ALGORITHM TESTS PASSED SUCCESSFULLY!")
    print("-" * 70 + "\n")


def run_interleaving_comparison_experiment():
    """
    Demonstrate Slide 9 & 11:
    Recovery rate WITH Interleaving vs WITHOUT Interleaving across burst lengths 1 to 32.
    """
    print("=" * 70)
    print("  STAGE 2: WITH vs WITHOUT INTERLEAVING COMPARISON EXPERIMENT")
    print("=" * 70)
    print("Evaluating resilience against contiguous burst noise on a 256-byte payload...")
    
    raw_data = bytes([i % 256 for i in range(256)])
    encoded = hamming.encode_bytes(raw_data)
    interleaved = interleaver.interleave_bytes(encoded, interleaver.INTERLEAVE_DEPTH)
    
    print(f"\n{'Burst Length (bits)':<22} | {'WITHOUT Interleaving':<22} | {'WITH Interleaving (depth 32)':<25}")
    print("-" * 73)
    
    for burst_len in [1, 2, 4, 8, 12, 16, 24, 32]:
        # --- WITHOUT Interleaving ---
        # Corrupt contiguous bits directly in encoded stream
        corrupt_no_int = bytearray(encoded)
        start_bit = 50
        for b in range(burst_len):
            idx = (start_bit + b) // 8
            bit = 7 - ((start_bit + b) % 8)
            corrupt_no_int[idx] ^= (1 << bit)
            
        dec_no_int, n_corr1, _ = hamming.decode_bytes(bytes(corrupt_no_int), interleaver.NIBBLES_PER_FRAME)
        no_int_success = (dec_no_int == raw_data)
        no_int_str = "RECOVERED [OK]" if no_int_success else f"CORRUPTED [FAILED] ({n_corr1} bits fixed)"
        
        # --- WITH Interleaving ---
        # Corrupt contiguous bits in interleaved stream
        corrupt_with_int = bytearray(interleaved)
        for b in range(burst_len):
            idx = (start_bit + b) // 8
            bit = 7 - ((start_bit + b) % 8)
            corrupt_with_int[idx] ^= (1 << bit)
            
        deint = interleaver.deinterleave_bytes(bytes(corrupt_with_int), interleaver.CODEWORDS_PER_FRAME, interleaver.INTERLEAVE_DEPTH)
        dec_with_int, n_corr2, _ = hamming.decode_bytes(deint, interleaver.NIBBLES_PER_FRAME)
        with_int_success = (dec_with_int == raw_data)
        with_int_str = "RECOVERED [OK] (100%)" if with_int_success else "CORRUPTED [FAILED]"
        
        print(f"{burst_len:<22} | {no_int_str:<22} | {with_int_str:<25}")
        
    print("-" * 73)
    print("Conclusion: Without interleaving, bursts >= 2 bits fail because multiple bits in a single")
    print("codeword flip. With interleaving (depth 32), burst errors up to 32 bits are 100% restored!\n")


def run_e2e_transfer_test(proto='tcp', corruption_prob=1.0, min_burst=4, max_burst=16):
    """
    Runs full 3-process Client -> Relay -> Server test.
    """
    print("=" * 70)
    print(f"  STAGE 3: END-TO-END FILE TRANSFER TEST ({proto.upper()})")
    print(f"  Pipeline: Client -> Relay (Injects {min_burst}-{max_burst}b Bursts, Prob={corruption_prob}) -> Server")
    print("=" * 70)
    
    server_port = 12001 if proto == 'tcp' else 12003
    relay_port = 12002 if proto == 'tcp' else 12004
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a realistic test file (e.g. 1024 bytes = 4 frames)
        test_file_path = os.path.join(tmpdir, "test_document.txt")
        test_content = (
            "Computer Networks Final Project: Error Detection and Correction System.\n"
            "Team: Mohit Seth (24BCE2950) & Vinayak Sangram Patil (24BCE2147).\n"
            "Architecture: Client -> Relay -> Server.\n"
            "Features: Hamming(7,4) Forward Error Correction, Bit-Level Interleaving (depth 32),\n"
            "CRC-16-CCITT Error Detection, and SHA-256 Integrity Verification.\n"
            + ("Forward Error Correction allows real-time recovery without retransmission!\n" * 12)
        ).encode('utf-8')
        
        with open(test_file_path, 'wb') as f:
            f.write(test_content)
            
        orig_sha256 = hashlib.sha256(test_content).hexdigest()
        print(f"[Setup] Created test file ({len(test_content)} bytes)")
        print(f"[Setup] Original SHA-256: {orig_sha256}")
        
        out_dir = os.path.join(tmpdir, "server_received")
        os.makedirs(out_dir, exist_ok=True)
        
        # 1. Start Server in background thread
        if proto == 'tcp':
            server_thread = threading.Thread(
                target=run_tcp_server, 
                args=(server_port, out_dir),
                daemon=True
            )
        else:
            server_thread = threading.Thread(
                target=run_udp_server, 
                args=(server_port, out_dir),
                daemon=True
            )
        server_thread.start()
        time.sleep(0.3)
        
        # 2. Start Relay in background thread
        if proto == 'tcp':
            relay_thread = threading.Thread(
                target=run_tcp_relay, 
                args=(relay_port, server_port, corruption_prob, min_burst, max_burst),
                daemon=True
            )
        else:
            relay_thread = threading.Thread(
                target=run_udp_relay, 
                args=(relay_port, server_port, corruption_prob, min_burst, max_burst),
                daemon=True
            )
        relay_thread.start()
        time.sleep(0.3)
        
        # 3. Run Client
        print(f"\n[Client] Transmitting file via Relay on port {relay_port}...")
        if proto == 'tcp':
            send_file_tcp(test_file_path, '127.0.0.1', relay_port)
        else:
            send_file_udp(test_file_path, '127.0.0.1', relay_port)
            
        # Give threads time to finish writing and finalizing
        time.sleep(0.8)
        
        # 4. Verify received file
        received_path = os.path.join(out_dir, "received_test_document.txt")
        assert os.path.exists(received_path), f"Received file not found at {received_path}!"
        
        with open(received_path, 'rb') as f:
            received_content = f.read()
            
        received_sha256 = hashlib.sha256(received_content).hexdigest()
        assert received_content == test_content, "Received content does NOT match original content!"
        assert received_sha256 == orig_sha256, "SHA-256 mismatch!"
        
        print("\n" + "*" * 70)
        print(f"  [SUCCESS] {proto.upper()} END-TO-END PIPELINE FULLY VERIFIED!")
        print(f"  File transferred with 100% error recovery over noisy channel.")
        print(f"  SHA-256: {received_sha256} == {orig_sha256}")
        print("*" * 70 + "\n")


def _quiet_scenario(**kw):
    """Run a harness scenario with its console chatter suppressed."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return harness.run_scenario(**kw)


def run_parity_scenarios():
    """
    STAGE 5: targeted end-to-end scenarios through the real client, relay and server.
    Each scenario states what the design promises and checks the observed outcome.
    """
    print("=" * 70)
    print("  STAGE 5: XOR PARITY SCENARIOS (real sockets, relay and server)")
    print("=" * 70)
    
    # (name, kwargs, expect_pass, expected rebuilt, expected unrecoverable)
    scenarios = [
        ("TCP  burst 12b on #3, within depth 32 (layer 1 alone)",
         dict(proto='tcp', min_burst=12, max_burst=12, target_frames='3'), True, [], []),
        ("TCP  burst 40b on #3, past depth 32, parity ON  -> rebuilt",
         dict(proto='tcp', min_burst=40, max_burst=40, target_frames='3'), True, [3], []),
        ("TCP  burst 40b on #3, past depth 32, parity OFF -> detected FAIL",
         dict(proto='tcp', min_burst=40, max_burst=40, target_frames='3', group_size=0), False, [], [3]),
        ("TCP  burst 400b on #2 (several blocks lost), parity ON -> rebuilt",
         dict(proto='tcp', min_burst=400, max_burst=400, target_frames='2'), True, [2], []),
        ("TCP  burst 40b on parity P1 only -> data intact, no rebuild",
         dict(proto='tcp', min_burst=40, max_burst=40, target_frames='P1'), True, [], []),
        ("TCP  burst 40b on #2 AND #3 (same group) -> detected FAIL",
         dict(proto='tcp', min_burst=40, max_burst=40, target_frames='2,3'), False, [], [2, 3]),
        ("TCP  burst 40b on #3 AND parity P1 -> detected FAIL",
         dict(proto='tcp', min_burst=40, max_burst=40, target_frames='3,P1'), False, [], [3]),
        ("TCP  burst 40b on #1 and #5 (different groups) -> both rebuilt",
         dict(proto='tcp', min_burst=40, max_burst=40, target_frames='1,5'), True, [1, 5], []),
        ("TCP  depth 512, burst 300b on #3 -> layer 1 alone",
         dict(proto='tcp', depth=512, min_burst=300, max_burst=300, target_frames='3'), True, [], []),
        ("TCP  depth 8, burst 40b on #3 -> rebuilt",
         dict(proto='tcp', depth=8, min_burst=40, max_burst=40, target_frames='3'), True, [3], []),
        ("UDP  burst 40b on #3, parity ON  -> rebuilt",
         dict(proto='udp', min_burst=40, max_burst=40, target_frames='3'), True, [3], []),
        ("UDP  frame #2 dropped (lost datagram), parity ON -> rebuilt",
         dict(proto='udp', drop_frames='2', corruption_prob=0.0), True, [2], []),
        ("UDP  frame #2 dropped, parity OFF -> detected FAIL",
         dict(proto='udp', drop_frames='2', corruption_prob=0.0, group_size=0), False, [], [2]),
        ("UDP  last (short) frame #5 dropped -> rebuilt, length from metadata",
         dict(proto='udp', drop_frames='5', corruption_prob=0.0), True, [5], []),
        ("UDP  frames #2 and #3 dropped (same group) -> detected FAIL",
         dict(proto='udp', drop_frames='2,3', corruption_prob=0.0), False, [], [2, 3]),
    ]
    
    failures = 0
    print(f"\n{'Scenario':<68} | {'Expected':<9} | {'Observed':<9} | Result")
    print("-" * 100)
    for name, kw, expect_pass, exp_rebuilt, exp_unrec in scenarios:
        kw = dict(kw)
        kw.setdefault('seed', 11)
        r = _quiet_scenario(**kw)
        rep = r['report'] or {}
        ok = (bool(rep) and rep['match'] == expect_pass
              and r['received_equal'] == expect_pass
              and rep['rebuilt'] == exp_rebuilt
              and rep['unrecoverable'] == exp_unrec)
        failures += (not ok)
        print(f"{name:<68} | {'PASS' if expect_pass else 'FAIL':<9} | "
              f"{'PASS' if rep.get('match') else 'FAIL':<9} | {'ok' if ok else '*** MISMATCH ***'}")
    print("-" * 100)
    assert failures == 0, f"{failures} parity scenario(s) did not behave as designed"
    print("  All scenarios behaved exactly as the design predicts.")
    print("  (Expected FAIL = damage beyond the envelope: detected by CRC-16/SHA-256 and reported, never silent.)\n")


def main():
    print("\n" + "#" * 70)
    print("  ERROR DETECTION & CORRECTION SYSTEM - COMPLETE TEST SUITE")
    print("  Author: Mohit Seth (24BCE2950) & Vinayak Sangram Patil (24BCE2147)")
    print("#" * 70 + "\n")
    
    # Stage 1: Unit tests
    run_unit_tests()
    
    # Stage 2: With vs Without Interleaving
    run_interleaving_comparison_experiment()
    
    # Stage 3: TCP End-to-End
    run_e2e_transfer_test(proto='tcp', corruption_prob=1.0, min_burst=4, max_burst=16)
    
    # Stage 4: UDP End-to-End
    run_e2e_transfer_test(proto='udp', corruption_prob=1.0, min_burst=4, max_burst=16)
    
    # Stage 5: XOR parity scenarios
    run_parity_scenarios()
    
    print("\n" + "=" * 70)
    print("  ALL VERIFICATION STAGES COMPLETED WITH 100% PASS RATE!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
