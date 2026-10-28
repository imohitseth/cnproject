# Error Detection & Correction - Reliable File Transfer over a Noisy Channel

Computer Networks project - Mohit Seth (24BCE2950), Vinayak Sangram Patil (24BCE2147)

Client -> Relay -> Server file transfer (TCP and UDP) where the relay injects burst errors
and the receiver repairs them **without retransmission**, using two protection layers:

| Layer | Where | Mechanism | Repairs |
|---|---|---|---|
| 1 (inner) | inside a frame | Hamming(7,4) + bit-level block interleaving (depth D, default 32) | any burst of up to D bits per 32-codeword block |
| 2 (outer) | across frames | one XOR parity frame per group of k = 4 data frames | any ONE bad or lost frame per group |
| detect | per frame / whole file | CRC-16-CCITT per frame, SHA-256 per file | decides what to trust; reports what cannot be repaired |

Frame = 8 B header (frame_id 4, orig_len 2, crc16 2) + 448 B payload (256 B -> 512 Hamming codewords
-> 16 interleaver blocks) = 456 B. Parity frames use the same layout, with
`frame_id = 0x80000000 | group_index`.

## Run everything

```bash
python3 run_tests.py        # unit tests + 15 end-to-end scenarios (real sockets), ~1 min
python3 demo_review.py      # 5-step live demo for the review  (--pause: wait for Enter, --verbose: full log)
python3 sweep.py            # burst-length experiment -> results/sweep_results.csv, results/sweep.png
```

Individual modules self-test: `python3 hamming.py`, `interleaver.py`, `framing.py`, `parity.py`,
`detection.py`, `channel_emulator.py`.

## Manual three-terminal demo

```bash
# terminal 1 - server
python3 -m src.server --port 9998 --output-dir received_files
# terminal 2 - relay: a 40-bit burst (past depth 32) on data frame 3 only
python3 -m src.relay --port 9999 --server-port 9998 --min-burst 40 --max-burst 40 --target-frames 3 --seed 3
# terminal 3 - client (demo_file.txt = 5 data frames + 2 parity frames)
python3 -m src.client demo_file.txt --port 9999
```

Things to vary:

* `--group-size 0` on the client turns parity OFF: the same burst now ends in a detected FAIL.
* `--target-frames 2,3` corrupts two frames of one group: detected, not repairable (design limit).
* `--depth 512` on the client: a 300-bit burst is repaired by layer 1 alone.
* UDP: add `--proto udp` to all three, and on the relay `--corruption-prob 0 --drop-frames 2`
  to lose a whole datagram; the parity frame rebuilds it.
* `--target-frames P1` corrupts the parity frame of group 1 (`P<n>` = parity of group n).

## What changed from Review 1

* `src/parity.py` (new) - XOR group builder and single-frame rebuild.
* `src/framing.py` - parity frame ids/helpers; metadata now carries `depth` and `group_size`.
* `src/client.py` / `src/server.py` - `--depth`, `--group-size`; server rebuilds a bad/missing frame,
  prints a layered report and returns it as a dict.
* `src/relay.py` - `--target-frames`, `--drop-frames` (UDP), `--seed`.
* `src/interleaver.py` - `VALID_DEPTHS`, `validate_depth`, tests for every depth and for depth+1 failure.
* `src/channel_emulator.py` - `corrupt_at()` deterministic burst.
* `src/harness.py` (new) - runs one real client/relay/server scenario in-process.
* `sweep.py`, `demo_review.py` (new); `run_tests.py` extended with Stage 5.

## Design envelope (state this at the review)

* Layer 1 guarantees bursts up to the depth per block. One more bit inside a block puts two errors in
  a codeword; Hamming then fails or miscorrects, and CRC-16 flags the frame.
* Layer 2 repairs one bad frame per group of 4. Two bad frames in a group (or a bad frame plus its
  parity frame) are detected and reported (SHA-256 mismatch), never silently accepted.
* The relay corrupts only encoded payloads; headers, metadata and END frames pass intact (headers are
  assumed separately protected). The relay emulates corruption that escapes lower-layer checksums.
* Cost: 5 frames x 456 B = 2280 B for 1024 B of data (about 2.2x on the wire).
* The TCP per-frame reply is flow control only; no frame is ever retransmitted.

## Sweep results (200 trials per cell, seed 1)

Recovery rate for a contiguous burst. "single" = burst inside one random data frame;
"stream" = burst anywhere in the group's concatenated frames (may span two frames).

| Burst (bits) | Hamming only | d=32 | d=512 | d=32 + XOR | d=512 + XOR |
|---|---|---|---|---|---|
| 1 | 100% | 100% | 100% | 100% | 100% |
| 2 | ~11% | 100% | 100% | 100% | 100% |
| 4 to 32 | 0% | 100% | 100% | 100% | 100% |
| 33 | 0% | ~14% | 100% | 100% | 100% |
| 64 | 0% | ~1% | 100% | 100% | 100% |
| 500 (single) | 0% | 0% | 100% | 100% | 100% |
| 513 (single) | 0% | 0% | 0% | 100% | 100% |
| 500 (stream) | 0% | 0% | 100% | ~88% | 100% |
| 1000 (stream) | 0% | 0% | ~1% | ~72% | 100% |

Silent corruption (CRC-16 passing a wrong frame): 0 in all trials.
Full tables: `results/sweep_results.csv`; plot: `results/sweep.png`.
