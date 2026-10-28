"""
Server Process - File Reception with Error Correction and Integrity Verification.

Receive path for every frame:
  de-interleave (depth from metadata) -> Hamming(7,4) decode -> CRC-16 check.

Recovery path (outer layer), run when the END frame arrives:
  for each group of k data frames, if exactly ONE frame failed its CRC-16 (or never
  arrived over UDP) and the group's parity frame is intact, rebuild it:
      Fx = P ^ (other frames of the group)
  Two or more bad frames in a group cannot be repaired; they are reported, and the
  whole-file SHA-256 gives the final PASS/FAIL verdict. Nothing is retransmitted.

Usage:
    python -m src.server [--proto tcp|udp] [--port PORT] [--output-dir DIR] [--verbose]
"""

import socket
import argparse
import sys
import os
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.framing import (parse_frame_header, parse_metadata_frame, verify_frame_crc,
                         is_parity_frame_id, parity_group_index, group_frame_ids,
                         frame_label, parity_frame_id,
                         FRAME_PAYLOAD_SIZE, HEADER_SIZE)
from src.protocol import wrap_message, unwrap_message, RecvBuffer
from src import hamming, interleaver, parity


class FileReceiver:
    """Receives, error-corrects, and reassembles file from frames."""
    
    def __init__(self, output_dir: str = '.', verbose: bool = False):
        self.output_dir = output_dir
        self.verbose = verbose
        self.metadata = None
        self.depth = interleaver.INTERLEAVE_DEPTH
        self.group_size = 0
        self.total_frames = 0
        self.received_frames = 0
        
        # Per data frame (key = frame_id)
        self.frames = {}          # trimmed raw payload (what goes into the file)
        self.padded = {}          # 256-byte padded payload (needed for XOR)
        self.crc_ok = {}          # CRC-16 verdict after Hamming
        self.crc_expected = {}    # CRC-16 from the (intact) header
        self.orig_len = {}
        # Per group (key = group index): (padded parity payload, crc_ok)
        self.parity_frames = {}
        
        # Statistics
        self.total_errors_corrected = 0
        self.frames_crc_passed = 0
        self.frames_crc_failed = 0
        self.frames_rebuilt = []
        self.frames_unrecoverable = []
        self.frame_stats = []
        self.report = None
    
    def process_metadata(self, frame_data: bytes):
        """Process metadata frame."""
        self.metadata = parse_metadata_frame(frame_data)
        self.total_frames = self.metadata['total_frames']
        self.depth = interleaver.validate_depth(self.metadata.get('depth', interleaver.INTERLEAVE_DEPTH))
        self.group_size = int(self.metadata.get('group_size', 0))
        print("-" * 65)
        print(f"[Server] Metadata Received:")
        print(f"  Filename:     {self.metadata['filename']}")
        print(f"  Filesize:     {self.metadata['filesize']} bytes")
        print(f"  Total frames: {self.total_frames}")
        print(f"  Interleave:   depth {self.depth}")
        print(f"  XOR parity:   " + (f"1 parity frame per {self.group_size} data frames" if self.group_size else "OFF"))
        print(f"  SHA-256:      {self.metadata['sha256']}")
        print("-" * 65)
    
    def _decode_payload(self, encoded_payload: bytes):
        """De-interleave + Hamming decode. Returns (padded_256, n_corrected, repair_details)."""
        deinterleaved = interleaver.deinterleave_bytes(
            encoded_payload, interleaver.CODEWORDS_PER_FRAME, self.depth)
        padded, n_corrected, _, repair_details = hamming.decode_bytes(
            deinterleaved, interleaver.NIBBLES_PER_FRAME, return_details=True)
        return padded, n_corrected, repair_details
    
    def process_data_frame(self, frame_id: int, frame_data: bytes):
        """Process a data or parity frame: de-interleave, Hamming decode, CRC-16 check."""
        header = frame_data[:HEADER_SIZE]
        encoded_payload = frame_data[HEADER_SIZE:]
        
        fid, orig_len, expected_crc = parse_frame_header(header)
        
        # Steps 1-2: bit-level de-interleaving, then Hamming(7,4) syndrome decoding
        padded, n_corrected, repair_details = self._decode_payload(encoded_payload)
        self.total_errors_corrected += n_corrected
        
        # Step 3: trim to original payload length, Step 4: CRC-16 verification
        raw_payload = padded[:orig_len]
        crc_ok = verify_frame_crc(raw_payload, expected_crc)
        label = frame_label(frame_id)
        
        status_str = "CRC-16: VALID [OK]" if crc_ok else "CRC-16: INVALID [FAIL]"
        corr_info = f"({n_corrected} bit errors corrected)" if n_corrected > 0 else "(clean)"
        
        if is_parity_frame_id(frame_id):
            self.parity_frames[parity_group_index(frame_id)] = (padded, crc_ok)
            print(f"  [Server] Parity {label:>3}: {status_str} {corr_info}")
        else:
            self.frames[frame_id] = raw_payload
            self.padded[frame_id] = padded
            self.crc_ok[frame_id] = crc_ok
            self.crc_expected[frame_id] = expected_crc
            self.orig_len[frame_id] = orig_len
            self.received_frames += 1
            if crc_ok:
                self.frames_crc_passed += 1
            else:
                self.frames_crc_failed += 1
            print(f"  [Server] Frame {label:>3}: {status_str} {corr_info}")
        
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
    
    def _expected_len(self, frame_id: int) -> int:
        """Payload length of data frame `frame_id`, derived from the file size."""
        remaining = self.metadata['filesize'] - (frame_id - 1) * FRAME_PAYLOAD_SIZE
        return max(0, min(FRAME_PAYLOAD_SIZE, remaining))
    
    def recover_with_parity(self):
        """Outer layer: rebuild one bad or missing frame per group from the XOR parity frame."""
        k = self.group_size
        if k <= 0:
            return
        n_groups = (self.total_frames + k - 1) // k
        print("-" * 65)
        print(f"[Server] Outer layer: XOR parity check ({n_groups} group(s) of up to {k} frames)")
        
        for g in range(n_groups):
            ids = group_frame_ids(g, k, self.total_frames)
            span = f"#{ids[0]}-#{ids[-1]}" if len(ids) > 1 else f"#{ids[0]}"
            plabel = frame_label(parity_frame_id(g))
            bad = [i for i in ids if i not in self.padded or not self.crc_ok.get(i, False)]
            
            if not bad:
                print(f"  Group {g + 1} (frames {span}): all frames OK")
                continue
            
            names = ", ".join(f"#{i}" + (" (missing)" if i not in self.padded else "") for i in bad)
            par = self.parity_frames.get(g)
            
            if len(bad) > 1:
                print(f"  Group {g + 1} (frames {span}): {len(bad)} bad frames [{names}] "
                      f"-> CANNOT rebuild (1 parity frame fixes 1 frame) [DETECTED, NOT REPAIRED]")
                self.frames_unrecoverable.extend(bad)
                continue
            if par is None or not par[1]:
                why = "not received" if par is None else "failed its own CRC-16"
                print(f"  Group {g + 1} (frames {span}): frame {names} bad and parity {plabel} {why} "
                      f"-> CANNOT rebuild [DETECTED, NOT REPAIRED]")
                self.frames_unrecoverable.extend(bad)
                continue
            
            known = [self.padded[i] if i not in bad else None for i in ids]
            idx, rebuilt = parity.rebuild_frame(known, par[0])
            fid = ids[idx]
            length = self.orig_len.get(fid, self._expected_len(fid))
            trimmed = rebuilt[:length]
            
            if fid in self.crc_expected:
                verified = verify_frame_crc(trimmed, self.crc_expected[fid])
                note = "CRC-16 VALID [OK]" if verified else "CRC-16 STILL INVALID [FAIL]"
            else:
                verified = True  # header never arrived (UDP loss); SHA-256 is the final check
                note = "header lost, verified by file SHA-256"
            
            if not verified:
                print(f"  Group {g + 1} (frames {span}): rebuilt #{fid} but {note}")
                self.frames_unrecoverable.append(fid)
                continue
            
            others = ", ".join(f"#{i}" for i in ids if i != fid)
            print(f"  Group {g + 1} (frames {span}): frame #{fid} "
                  f"{'missing' if fid not in self.padded else 'failed CRC-16'} "
                  f"-> REBUILT = {plabel} ^ {others or '(none)'} -> {note}")
            self.frames[fid] = trimmed
            self.padded[fid] = rebuilt
            self.crc_ok[fid] = True
            self.frames_rebuilt.append(fid)
    
    def finalize(self) -> bool:
        """Run parity recovery, reassemble the file and verify it end-to-end via SHA-256."""
        if not self.metadata:
            print("[Server] Error: No metadata received before finalize.")
            return False
        
        self.recover_with_parity()
        
        print("-" * 65)
        print(f"[Server] Reassembling {self.total_frames} frames...")
        
        file_data = bytearray()
        for frame_id in range(1, self.total_frames + 1):
            if frame_id in self.frames:
                file_data.extend(self.frames[frame_id])
            else:
                print(f"  [Server] Warning: Missing frame #{frame_id}!")
                file_data.extend(b'\x00' * self._expected_len(frame_id))
        
        final_bytes = bytes(file_data[:self.metadata['filesize']])
        out_name = f"received_{self.metadata['filename']}"
        output_path = os.path.join(self.output_dir, out_name)
        with open(output_path, 'wb') as f:
            f.write(final_bytes)
            
        received_sha256 = hashlib.sha256(final_bytes).hexdigest()
        expected_sha256 = self.metadata['sha256']
        match = (received_sha256 == expected_sha256)
        
        bad_final = sorted(set(self.frames_unrecoverable) |
                           {i for i in range(1, self.total_frames + 1)
                            if i not in self.frames or not self.crc_ok.get(i, False)})
        
        print("\n" + "=" * 65)
        print("          END-TO-END TRANSFER & VERIFICATION REPORT          ")
        print("=" * 65)
        print(f"  Target File:              {self.metadata['filename']}")
        print(f"  Saved To:                 {output_path}")
        print(f"  Original Size:            {self.metadata['filesize']} bytes")
        print(f"  Data Frames Received:     {self.received_frames} / {self.total_frames}")
        print(f"  Layer 1 (Hamming+interleave, depth {self.depth}):")
        print(f"    Bit errors corrected:   {self.total_errors_corrected}")
        print(f"    Frames CRC PASS:        {self.frames_crc_passed}")
        print(f"    Frames CRC FAIL:        {self.frames_crc_failed}  (sent on to layer 2)")
        print(f"  Layer 2 (XOR parity, k = {self.group_size or 'off'}):")
        print(f"    Frames rebuilt:         {len(self.frames_rebuilt)}" +
              (f"  {['#%d' % i for i in sorted(self.frames_rebuilt)]}" if self.frames_rebuilt else ""))
        print(f"    Frames unrecoverable:   {len(bad_final)}" +
              (f"  {['#%d' % i for i in bad_final]}" if bad_final else ""))
        print(f"  Expected SHA-256:         {expected_sha256}")
        print(f"  Received SHA-256:         {received_sha256}")
        print("-" * 65)
        if match:
            print("  VERDICT: [PASS] - FILE INTEGRITY 100% VERIFIED!")
            if self.frames_rebuilt:
                print("  Layer 1 + XOR parity restored all data without retransmission.")
            else:
                print("  Forward Error Correction restored all data without retransmission.")
        else:
            print("  VERDICT: [FAIL] - HASH MISMATCH DETECTED (damage beyond the design envelope)!")
            if bad_final:
                print(f"  Detected bad frames: {['#%d' % i for i in bad_final]} - reported, not silently accepted.")
        print("=" * 65 + "\n")
        
        self.report = {
            'match': match,
            'sha256_expected': expected_sha256,
            'sha256_received': received_sha256,
            'output_path': output_path,
            'total_frames': self.total_frames,
            'received_frames': self.received_frames,
            'bit_errors_corrected': self.total_errors_corrected,
            'crc_failed_after_hamming': self.frames_crc_failed,
            'rebuilt': sorted(self.frames_rebuilt),
            'unrecoverable': bad_final,
        }
        return match


def run_tcp_server(port: int, output_dir: str, verbose: bool = False):
    """Run TCP server with streaming RecvBuffer. Returns the receiver's report dict."""
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
                    frame_id, _, _ = parse_frame_header(frame_data[:8])
                    receiver.process_data_frame(frame_id, frame_data)
                    conn.sendall(wrap_message(b'\x11'))
                elif msg_type == 3:
                    match = receiver.finalize()
                    conn.sendall(wrap_message(b'\x12' + (b'\x01' if match else b'\x00')))
                    return receiver.report
    finally:
        conn.close()
        sock.close()
    return receiver.report


def run_udp_server(port: int, output_dir: str, verbose: bool = False):
    """Run UDP server. Returns the receiver's report dict."""
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
                frame_id, _, _ = parse_frame_header(frame_data[:8])
                receiver.process_data_frame(frame_id, frame_data)
                sock.sendto(wrap_message(b'\x11'), addr)
            elif msg_type == 3:
                match = receiver.finalize()
                sock.sendto(wrap_message(b'\x12' + (b'\x01' if match else b'\x00')), addr)
                return receiver.report
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
