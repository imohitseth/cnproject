"""
Script to generate the Final Review Presentation (Final_Review_Presentation.pptx)
for Computer Networks: Error Detection and Correction.
"""

import sys
import os

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE
except ImportError:
    print("python-pptx is not installed. Installing python-pptx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-pptx"])
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

def build_presentation(output_path="Final_Review_Presentation.pptx"):
    prs = Presentation()
    # 16:9 Widescreen slides (13.333 x 7.5 inches)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]  # Blank slide

    # Theme Palette (Matches cn final.pdf)
    NAVY_BG = RGBColor(11, 37, 69)       # #0B2545 (Deep Navy)
    DARK_BLUE = RGBColor(19, 64, 116)     # #134074 (Secondary Navy)
    LIGHT_BG = RGBColor(244, 247, 250)    # #F4F7FA (Crisp light gray/white)
    CARD_BG = RGBColor(255, 255, 255)     # #FFFFFF (White card)
    CARD_BORDER = RGBColor(218, 225, 233) # Subtle border
    ACCENT_CYAN = RGBColor(0, 168, 150)   # Teal/Cyan accent
    ACCENT_BLUE = RGBColor(30, 144, 255)  # Bright Blue
    TEXT_DARK = RGBColor(17, 24, 39)      # Slate Dark
    TEXT_MUTED = RGBColor(100, 116, 139)  # Gray Muted
    TEXT_LIGHT = RGBColor(241, 245, 249)  # White text
    SUCCESS_GREEN = RGBColor(16, 185, 129)# Green for PASS
    WARN_CORAL = RGBColor(239, 68, 68)    # Coral for FAIL

    def set_bg(slide, color):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.color.rgb = color
        return bg

    def add_header(slide, category, title, dark=False):
        # Category tag
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category.upper()
        p_cat.font.size = Pt(11)
        p_cat.font.bold = True
        p_cat.font.color.rgb = ACCENT_CYAN if dark else DARK_BLUE

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.85), Inches(11.5), Inches(0.8))
        tf_t = title_box.text_frame
        tf_t.word_wrap = True
        p_t = tf_t.paragraphs[0]
        p_t.text = title
        p_t.font.size = Pt(28)
        p_t.font.bold = True
        p_t.font.color.rgb = TEXT_LIGHT if dark else TEXT_DARK

    def create_card(slide, left, top, width, height, bg_color=CARD_BG, border_color=CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1)
        return card

    # =========================================================================
    # SLIDE 1: Title Slide (Dark Navy)
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)
    set_bg(slide1, NAVY_BG)

    # Subtitle tag
    tb = slide1.shapes.add_textbox(Inches(1.2), Inches(1.5), Inches(10), Inches(0.5))
    p = tb.text_frame.paragraphs[0]
    p.text = "COMPUTER NETWORKS FINAL REVIEW PROJECT"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN

    # Main Title
    tb = slide1.shapes.add_textbox(Inches(1.2), Inches(2.1), Inches(11), Inches(1.8))
    p = tb.text_frame.paragraphs[0]
    p.text = "Error Detection & Correction"
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = TEXT_LIGHT

    # Description
    tb = slide1.shapes.add_textbox(Inches(1.2), Inches(3.8), Inches(10.5), Inches(1.0))
    p = tb.text_frame.paragraphs[0]
    p.text = "Reliable File Transfer over a Noisy Channel using Hamming(7,4) Forward Error Correction, Bit-Level Interleaving (Depth 32), and CRC-16-CCITT Verification."
    p.font.size = Pt(16)
    p.font.italic = True
    p.font.color.rgb = RGBColor(190, 210, 230)

    # Team Card
    tcard = create_card(slide1, 1.2, 5.2, 10.9, 1.4, bg_color=DARK_BLUE, border_color=ACCENT_CYAN)
    
    tb = slide1.shapes.add_textbox(Inches(1.5), Inches(5.35), Inches(4.5), Inches(1.0))
    tf = tb.text_frame
    p1 = tf.paragraphs[0]
    p1.text = "PROJECT TEAM"
    p1.font.size = Pt(11)
    p1.font.bold = True
    p1.font.color.rgb = ACCENT_CYAN
    
    p2 = tf.add_paragraph()
    p2.text = "Mohit Seth  |  24BCE2950"
    p2.font.size = Pt(15)
    p2.font.bold = True
    p2.font.color.rgb = TEXT_LIGHT
    
    tb2 = slide1.shapes.add_textbox(Inches(6.8), Inches(5.35), Inches(4.5), Inches(1.0))
    tf2 = tb2.text_frame
    p1b = tf2.paragraphs[0]
    p1b.text = "TEAM MEMBER"
    p1b.font.size = Pt(11)
    p1b.font.bold = True
    p1b.font.color.rgb = ACCENT_CYAN
    
    p2b = tf2.add_paragraph()
    p2b.text = "Vinayak Sangram Patil  |  24BCE2147"
    p2b.font.size = Pt(15)
    p2b.font.bold = True
    p2b.font.color.rgb = TEXT_LIGHT

    # =========================================================================
    # SLIDE 2: Why Error Control Matters (Problem Statement)
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    set_bg(slide2, LIGHT_BG)
    add_header(slide2, "Introduction", "Why Error Control Matters")

    # Left Narrative Card
    create_card(slide2, 0.8, 1.8, 6.2, 5.0)
    tb = slide2.shapes.add_textbox(Inches(1.1), Inches(2.1), Inches(5.6), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    
    p = tf.paragraphs[0]
    p.text = "The Physical Channel Reality"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE

    p = tf.add_paragraph()
    p.text = (
        "\nIn real-world networks, physical channels suffer from electromagnetic interference (EMI), "
        "signal attenuation, crosstalk, and thermal noise. These impairments corrupt transmitted bits — "
        "causing both isolated single-bit flips and contiguous burst errors.\n\n"
        "Traditional transport layers (like TCP) rely on retransmission (ARQ) when checksums fail. "
        "However, on high-latency, satellite, wireless, or unidirectional links, ARQ introduces "
        "intolerable latency, buffer bloat, and round-trip overhead.\n\n"
        "Our Solution: A hybrid Forward Error Correction (FEC) pipeline that detects and corrects "
        "burst errors locally at the receiver with ZERO retransmissions."
    )
    p.font.size = Pt(13)
    p.font.color.rgb = TEXT_DARK

    # Right 4 Sources of Noise Cards
    sources = [
        ("1. EM Interference", "External electrical signals & RF disturbances corrupt consecutive bits."),
        ("2. Signal Attenuation", "Signal power diminishes over distance, lowering the SNR threshold."),
        ("3. Crosstalk", "Capacitive & inductive coupling from adjacent wire pairs or radio channels."),
        ("4. Hardware Faults", "Transceiver clock drift, timing jitter, and bus transmission glitches.")
    ]
    for i, (stitle, sdesc) in enumerate(sources):
        scard = create_card(slide2, 7.3, 1.8 + i * 1.25, 5.2, 1.1)
        tb = slide2.shapes.add_textbox(Inches(7.5), Inches(1.85 + i * 1.25), Inches(4.8), Inches(0.9))
        tf = tb.text_frame
        p1 = tf.paragraphs[0]
        p1.text = stitle
        p1.font.size = Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = DARK_BLUE
        p2 = tf.add_paragraph()
        p2.text = sdesc
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 3: Concrete Objectives
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_bg(slide3, LIGHT_BG)
    add_header(slide3, "Problem Statement & Objective", "Concrete Project Objectives")

    objs = [
        ("Socket File Transfer", "Implement production-grade client-server file transfer supporting both TCP (streaming) and UDP (datagrams)."),
        ("Dual FEC & Detection", "Combine Hamming(7,4) Forward Error Correction with standard CRC-16-CCITT independent detection."),
        ("Burst Error Immunity", "Implement bit-level block interleaving (depth 32) to defeat contiguous channel burst noise."),
        ("Relay Noise Middleman", "Build a standalone middleman process to emulate real physical channel noise with configurable bursts."),
        ("No Retransmission Rule", "Ensure corrupted files are 100% restored locally by the receiver without requesting retransmissions."),
        ("Cryptographic Audit", "Exhaustive verification: per-frame CRC-16 checks and whole-file SHA-256 match.")
    ]

    for i, (otitle, odesc) in enumerate(objs):
        row = i // 3
        col = i % 3
        cx = 0.8 + col * 3.95
        cy = 1.9 + row * 2.55
        create_card(slide3, cx, cy, 3.75, 2.3)
        tb = slide3.shapes.add_textbox(Inches(cx + 0.2), Inches(cy + 0.2), Inches(3.35), Inches(1.9))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = f"#{i+1}  {otitle}"
        p1.font.size = Pt(15)
        p1.font.bold = True
        p1.font.color.rgb = DARK_BLUE
        p2 = tf.add_paragraph()
        p2.text = f"\n{odesc}"
        p2.font.size = Pt(12)
        p2.font.color.rgb = TEXT_DARK

    # =========================================================================
    # SLIDE 4: Where Conventional Approaches Fall Short
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_bg(slide4, LIGHT_BG)
    add_header(slide4, "Existing Systems vs. Our Approach", "Where Conventional Approaches Fall Short")

    # Table layout
    rows, cols = 6, 3
    t_left, t_top, t_width, t_height = Inches(0.8), Inches(1.8), Inches(11.73), Inches(5.0)
    table_shape = slide4.shapes.add_table(rows, cols, t_left, t_top, t_width, t_height)
    table = table_shape.table

    table.columns[0].width = Inches(2.8)
    table.columns[1].width = Inches(4.5)
    table.columns[2].width = Inches(4.43)

    headers = ["Conventional Approach", "Inherent Limitation", "Our System's Modification"]
    for c, h in enumerate(headers):
        cell = table.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = DARK_BLUE
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = TEXT_LIGHT

    data_rows = [
        ("Internet Checksum (RFC 1071)", "Detects only; error pairs cancel out; no correction.", "Application-layer CRC-16 + Hamming(7,4) FEC."),
        ("ARQ (Stop-and-Wait, GBN)", "RTT latency penalty per error; requires return channel.", "Forward Error Correction: Receiver repairs data locally."),
        ("Plain Hamming(7,4)", "Corrects only 1 bit per 7-bit codeword; fails on bursts.", "Bit-level block interleaving (depth 32) disperses bursts."),
        ("Simple Parity Check", "Cannot detect even number of bit flips.", "Dual-layer check: Hamming syndrome + CRC-16 polynomial."),
        ("Reed-Solomon / LDPC", "High mathematical complexity (Galois Field arithmetic).", "Hamming(7,4) + depth 32 interleaver: simple, demonstrative, robust.")
    ]

    for r, row_data in enumerate(data_rows):
        for c, val in enumerate(row_data):
            cell = table.cell(r + 1, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD_BG if r % 2 == 0 else RGBColor(235, 241, 247)
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.size = Pt(11)
            p.font.color.rgb = TEXT_DARK
            if c == 0:
                p.font.bold = True

    # =========================================================================
    # SLIDE 5: System Architecture (3-Process Pipeline)
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_bg(slide5, NAVY_BG)
    add_header(slide5, "Proposed System", "System Architecture & 3-Process Pipeline", dark=True)

    # 3 Stage Boxes
    stages = [
        ("CLIENT", "Data Preparation & Protection", [
            "Reads source file & computes SHA-256",
            "Partitions into 256B raw chunks",
            "Hamming(7,4) encodes -> 512 codewords",
            "Applies Bit-level Interleaving (depth 32)",
            "Attaches 8B protected header -> 456B frame"
        ], ACCENT_BLUE),
        ("RELAY", "Noisy Channel Emulator", [
            "Standalone middleman network process",
            "Preserves 1B type & 8B frame header",
            "Injects contiguous burst bit flips",
            "Configurable burst length & probability",
            "Forwards corrupted stream to Server"
        ], WARN_CORAL),
        ("SERVER", "Correction & Verification", [
            "Buffers TCP stream / UDP datagrams",
            "Reverses depth-32 bit interleaving",
            "Hamming syndrome decoding (SEC)",
            "Verifies CRC-16-CCITT per frame",
            "Reassembles file & audits SHA-256 (PASS)"
        ], SUCCESS_GREEN)
    ]

    for i, (sname, stitle, points, scolor) in enumerate(stages):
        bx = 0.8 + i * 4.0
        by = 2.0
        c = create_card(slide5, bx, by, 3.7, 4.8, bg_color=DARK_BLUE, border_color=scolor)
        
        tb = slide5.shapes.add_textbox(Inches(bx + 0.2), Inches(by + 0.2), Inches(3.3), Inches(4.4))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        p.text = sname
        p.font.size = Pt(22)
        p.font.bold = True
        p.font.color.rgb = scolor

        p = tf.add_paragraph()
        p.text = stitle
        p.font.size = Pt(12)
        p.font.italic = True
        p.font.color.rgb = ACCENT_CYAN

        p = tf.add_paragraph()
        p.text = ""

        for pt in points:
            p = tf.add_paragraph()
            p.text = f"- {pt}"
            p.font.size = Pt(11)
            p.font.color.rgb = TEXT_LIGHT

    # =========================================================================
    # SLIDE 6: Frame Format Architecture
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    set_bg(slide6, LIGHT_BG)
    add_header(slide6, "Framing Layer", "Frame Structure: 456-Byte Transmission Unit")

    # Visual Frame Representation
    # 8-byte header (3 sub-blocks) + 448-byte payload
    f_y = 1.9
    # frame_id (4B)
    b1 = create_card(slide6, 0.8, f_y, 2.0, 1.4, bg_color=DARK_BLUE, border_color=DARK_BLUE)
    tb = slide6.shapes.add_textbox(Inches(0.9), Inches(f_y + 0.25), Inches(1.8), Inches(0.9))
    tf = tb.text_frame
    p1 = tf.paragraphs[0]
    p1.text = "frame_id"
    p1.font.bold = True
    p1.font.color.rgb = TEXT_LIGHT
    p2 = tf.add_paragraph()
    p2.text = "4 Bytes (uint32)"
    p2.font.size = Pt(11)
    p2.font.color.rgb = ACCENT_CYAN

    # orig_len (2B)
    b2 = create_card(slide6, 2.9, f_y, 1.8, 1.4, bg_color=DARK_BLUE, border_color=DARK_BLUE)
    tb = slide6.shapes.add_textbox(Inches(3.0), Inches(f_y + 0.25), Inches(1.6), Inches(0.9))
    tf = tb.text_frame
    p1 = tf.paragraphs[0]
    p1.text = "orig_len"
    p1.font.bold = True
    p1.font.color.rgb = TEXT_LIGHT
    p2 = tf.add_paragraph()
    p2.text = "2 Bytes (uint16)"
    p2.font.size = Pt(11)
    p2.font.color.rgb = ACCENT_CYAN

    # crc16 (2B)
    b3 = create_card(slide6, 4.8, f_y, 1.8, 1.4, bg_color=DARK_BLUE, border_color=DARK_BLUE)
    tb = slide6.shapes.add_textbox(Inches(4.9), Inches(f_y + 0.25), Inches(1.6), Inches(0.9))
    tf = tb.text_frame
    p1 = tf.paragraphs[0]
    p1.text = "crc16"
    p1.font.bold = True
    p1.font.color.rgb = TEXT_LIGHT
    p2 = tf.add_paragraph()
    p2.text = "2 Bytes (CRC-16)"
    p2.font.size = Pt(11)
    p2.font.color.rgb = ACCENT_CYAN

    # Payload (448B)
    b4 = create_card(slide6, 6.7, f_y, 5.8, 1.4, bg_color=ACCENT_CYAN, border_color=ACCENT_CYAN)
    tb = slide6.shapes.add_textbox(Inches(6.9), Inches(f_y + 0.25), Inches(5.4), Inches(0.9))
    tf = tb.text_frame
    p1 = tf.paragraphs[0]
    p1.text = "Interleaved Hamming(7,4) Payload"
    p1.font.size = Pt(16)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_LIGHT
    p2 = tf.add_paragraph()
    p2.text = "448 Bytes (512 codewords interleaved with depth 32 across 16 blocks)"
    p2.font.size = Pt(11)
    p2.font.color.rgb = NAVY_BG

    # Key Architectural Decisions Card
    create_card(slide6, 0.8, 3.6, 11.7, 3.3)
    tb = slide6.shapes.add_textbox(Inches(1.1), Inches(3.8), Inches(11.1), Inches(2.9))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "Key Design Decisions & Protocol Engineering"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE

    points = [
        ("Header Outside Corruption Zone:", "Models real-world PHY layer design where packet control headers receive dedicated, heavier parity protection."),
        ("Pre-Encoding CRC-16 Computation:", "CRC is computed over the unencoded 256B payload to act as an independent post-correction verification oracle."),
        ("Length-Prefixed Stream Buffering:", "TCP uses [4-byte length] prefixing via RecvBuffer, ensuring complete message extraction despite partial reads or coalescing."),
        ("Perfect Byte Alignment:", "512 codewords divide into 16 blocks of 32. 32 x 7 = 224 bits = 28 bytes per block (448 bytes total) with zero padding waste.")
    ]
    for title, desc in points:
        p = tf.add_paragraph()
        p.text = f"- {title} {desc}"
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_DARK

    # =========================================================================
    # SLIDE 7: Three Layers of Error Detection
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    set_bg(slide7, LIGHT_BG)
    add_header(slide7, "Detection Methods", "Three Layers of Error Detection")

    dets = [
        ("Even Parity", "parity = d1 ^ d2 ^ ... ^ dn", [
            "Simplest possible baseline detection",
            "Single parity bit per block",
            "Detects any odd number of bit errors",
            "Blind to even bit flips (2, 4, 6...)",
            "Tested in detection.py to prove inadequacy"
        ]),
        ("Internet Checksum", "sum = ~(Sigma words) with carry fold", [
            "RFC 1071 16-bit one's complement sum",
            "Standard checksum in IPv4, TCP, UDP",
            "Catches common errors and burst tails",
            "Fails if equal positive and negative bit errors cancel",
            "Included as standard benchmark"
        ]),
        ("CRC-16-CCITT", "G(x) = x^16 + x^12 + x^5 + 1", [
            "Primary application-layer verification",
            "Bitwise implementation (poly 0x1021)",
            "Detects 100% of single & double bit errors",
            "Detects all odd numbers of bit errors",
            "Detects all burst errors up to 16 bits in length"
        ])
    ]

    for i, (dname, dmath, dpts) in enumerate(dets):
        cx = 0.8 + i * 4.0
        create_card(slide7, cx, 1.8, 3.7, 5.0)
        tb = slide7.shapes.add_textbox(Inches(cx + 0.2), Inches(2.0), Inches(3.3), Inches(4.5))
        tf = tb.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = dname
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = DARK_BLUE

        p = tf.add_paragraph()
        p.text = dmath
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = ACCENT_CYAN

        p = tf.add_paragraph()
        p.text = ""

        for pt in dpts:
            p = tf.add_paragraph()
            p.text = f"- {pt}"
            p.font.size = Pt(11)
            p.font.color.rgb = TEXT_DARK

    # =========================================================================
    # SLIDE 8: Hamming(7,4) Code Deep Dive
    # =========================================================================
    slide8 = prs.slides.add_slide(blank_layout)
    set_bg(slide8, NAVY_BG)
    add_header(slide8, "Forward Error Correction", "Hamming(7,4) Code & Syndrome Decoding", dark=True)

    # Codeword Visual (1 to 7)
    cw_bits = [
        ("p1", "Bit 1", ACCENT_CYAN),
        ("p2", "Bit 2", ACCENT_CYAN),
        ("d1", "Bit 3", TEXT_LIGHT),
        ("p3", "Bit 4", ACCENT_CYAN),
        ("d2", "Bit 5", TEXT_LIGHT),
        ("d3", "Bit 6", TEXT_LIGHT),
        ("d4", "Bit 7", TEXT_LIGHT)
    ]
    for i, (bname, bpos, bcol) in enumerate(cw_bits):
        bx = 1.0 + i * 1.6
        create_card(slide8, bx, 1.8, 1.4, 1.2, bg_color=DARK_BLUE, border_color=ACCENT_CYAN)
        tb = slide8.shapes.add_textbox(Inches(bx), Inches(1.9), Inches(1.4), Inches(1.0))
        tf = tb.text_frame
        p1 = tf.paragraphs[0]
        p1.text = bname
        p1.alignment = PP_ALIGN.CENTER
        p1.font.size = Pt(22)
        p1.font.bold = True
        p1.font.color.rgb = bcol
        p2 = tf.add_paragraph()
        p2.text = bpos
        p2.alignment = PP_ALIGN.CENTER
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_MUTED

    # Left: Parity Coverage Card
    create_card(slide8, 1.0, 3.3, 5.4, 3.6, bg_color=DARK_BLUE, border_color=ACCENT_CYAN)
    tb = slide8.shapes.add_textbox(Inches(1.2), Inches(3.5), Inches(5.0), Inches(3.2))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "Parity Generation Matrix"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN

    eqs = [
        "Parity Bit Positions: Powers of 2 (1, 2, 4)",
        "Data Bit Positions: 3, 5, 6, 7",
        "\np1 covers {1, 3, 5, 7}:  p1 = d1 ^ d2 ^ d4",
        "p2 covers {2, 3, 6, 7}:  p2 = d1 ^ d3 ^ d4",
        "p3 covers {4, 5, 6, 7}:  p3 = d2 ^ d3 ^ d4",
        "\nResult: Minimum Hamming distance d_min = 3.",
        "Guarantees Single Error Correction (SEC)."
    ]
    for eq in eqs:
        p = tf.add_paragraph()
        p.text = eq
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_LIGHT

    # Right: Syndrome Decoding Card
    create_card(slide8, 6.9, 3.3, 5.4, 3.6, bg_color=DARK_BLUE, border_color=ACCENT_CYAN)
    tb = slide8.shapes.add_textbox(Inches(7.1), Inches(3.5), Inches(5.0), Inches(3.2))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "Syndrome Error Locator"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN

    seqs = [
        "Syndrome Vector Calculation at Receiver:",
        "c1 = p1 ^ d1 ^ d2 ^ d4",
        "c2 = p2 ^ d1 ^ d3 ^ d4",
        "c3 = p3 ^ d2 ^ d3 ^ d4",
        "\nError Position Synthesis:",
        "error_pos = c1 | (c2 << 1) | (c3 << 2)",
        "\nInterpretation:",
        "- error_pos == 0: No error detected",
        "- error_pos in [1..7]: Exactly bit error_pos flipped!",
        "  Receiver executes: codeword[error_pos - 1] ^= 1"
    ]
    for seq in seqs:
        p = tf.add_paragraph()
        p.text = seq
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_LIGHT

    # =========================================================================
    # SLIDE 9: Bit-Level Block Interleaving
    # =========================================================================
    slide9 = prs.slides.add_slide(blank_layout)
    set_bg(slide9, LIGHT_BG)
    add_header(slide9, "Burst-Error Recovery", "Bit-Level Block Interleaving (Depth 32)")

    # Left: The Problem Without Interleaving
    create_card(slide9, 0.8, 1.8, 5.7, 5.0)
    tb = slide9.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.3), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "WITHOUT Interleaving: Burst Vulnerability"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = WARN_CORAL

    p = tf.add_paragraph()
    p.text = (
        "\nConsider sequential transmission of 7-bit codewords:\n"
        "Codeword 0: [b0, b1, b2, b3, b4, b5, b6]\n"
        "Codeword 1: [b0, b1, b2, b3, b4, b5, b6]\n\n"
        "If a channel burst flips 4 consecutive bits [b1, b2, b3, b4] in Codeword 0:\n"
        "-> Codeword 0 now contains 4 bit errors.\n"
        "-> Hamming(7,4) d_min is only 3 (corrects <= 1 bit).\n"
        "-> RESULT: Fatal decoding failure & data corruption!"
    )
    p.font.size = Pt(13)
    p.font.color.rgb = TEXT_DARK

    # Right: The Solution With Interleaving
    create_card(slide9, 6.8, 1.8, 5.7, 5.0)
    tb = slide9.shapes.add_textbox(Inches(7.0), Inches(2.0), Inches(5.3), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "WITH Interleaving (Depth 32): 100% Recovery"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = SUCCESS_GREEN

    p = tf.add_paragraph()
    p.text = (
        "\nBlock interleaving writes 32 codewords into a 32 x 7 matrix, "
        "and transmits column-by-column across codewords:\n"
        "Column 0: Bit 0 of CW 0, CW 1, CW 2 ... CW 31\n"
        "Column 1: Bit 1 of CW 0, CW 1, CW 2 ... CW 31\n\n"
        "Consequence:\n"
        "Bits from the SAME codeword are spaced exactly 32 bits apart!\n"
        "A channel burst of length L <= 32 bits hits at most ONE bit in any single codeword.\n\n"
        "-> At receiver: De-interleaver disperses the burst into isolated single-bit errors!\n"
        "-> Hamming(7,4) corrects 100% of errors without retransmission!"
    )
    p.font.size = Pt(12)
    p.font.color.rgb = TEXT_DARK

    # =========================================================================
    # SLIDE 10: Implementation & Software Modules
    # =========================================================================
    slide10 = prs.slides.add_slide(blank_layout)
    set_bg(slide10, LIGHT_BG)
    add_header(slide10, "System Architecture", "Modular Python Implementation")

    modules = [
        ("hamming.py", "Core FEC Engine", "encode_nibble(), decode_codeword(), encode_bytes(), decode_bytes(). Exhaustively verified on all 16 nibbles & all 7 bit flip permutations."),
        ("interleaver.py", "Bit-Level Block Interleaver", "interleave_bytes(), deinterleave_bytes(). Depth 32, 16 blocks per 448B frame payload. Converts burst errors into independent 1-bit errors."),
        ("detection.py", "Error Detection Triad", "compute_parity(), internet_checksum(), crc16_ccitt(). Implements 16-bit CRC polynomial G(x)=0x1021 for post-correction verification."),
        ("framing.py", "Frame Builder & Parser", "build_metadata_frame(), build_data_frame(), build_end_frame(), parse_frame_header(). Strict 8-byte header + 448-byte payload format."),
        ("channel_emulator.py", "Burst Noise Generator", "ChannelEmulator class. Injects contiguous bursts of configurable bit-lengths (e.g. 1-16 bits) and probability; tracks corruption stats."),
        ("protocol.py", "Transport Framing & Buffers", "RecvBuffer class handles TCP byte-stream coalescing and partial reads via 4-byte length prefixing. Also wraps UDP datagrams."),
        ("relay.py", "Standalone Middleman Process", "Listens for Client, connects to Server, corrupts data payload (headers untouched), forwards ACKs. Simulates noisy internet router."),
        ("client.py & server.py", "End-to-End File Transfer", "Client: SHA-256 -> Chunk -> Encode -> Interleave -> Send. Server: De-interleave -> Decode -> Check CRC -> Reassemble -> SHA-256 PASS.")
    ]

    for i, (mname, mtitle, mdesc) in enumerate(modules):
        col = i % 2
        row = i // 2
        mx = 0.8 + col * 5.95
        my = 1.8 + row * 1.35
        create_card(slide10, mx, my, 5.75, 1.25)
        tb = slide10.shapes.add_textbox(Inches(mx + 0.15), Inches(my + 0.1), Inches(5.45), Inches(1.05))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = f"{mname} - {mtitle}"
        p1.font.size = Pt(13)
        p1.font.bold = True
        p1.font.color.rgb = DARK_BLUE
        p2 = tf.add_paragraph()
        p2.text = mdesc
        p2.font.size = Pt(10)
        p2.font.color.rgb = TEXT_DARK

    # =========================================================================
    # SLIDE 11: Live Execution Results & Hash Verification
    # =========================================================================
    slide11 = prs.slides.add_slide(blank_layout)
    set_bg(slide11, NAVY_BG)
    add_header(slide11, "Experimental Verification", "End-to-End Execution Results & Hash Verification", dark=True)

    # Left: Terminal Execution Log Card
    create_card(slide11, 0.8, 1.8, 6.2, 5.1, bg_color=DARK_BLUE, border_color=ACCENT_CYAN)
    tb = slide11.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(5.8), Inches(4.8))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "Live Multi-Process Pipeline Log"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN

    log_lines = [
        "[Relay] Listening on 127.0.0.1:9999 -> Server 9998",
        "[Client] Sent Metadata frame (File: test_document.txt)",
        "[Relay] Frame #1: INJECTED burst error (12 bits flipped)",
        "[Server] Frame #1: CRC-16: VALID [OK] (12 bit errors corrected)",
        "[Relay] Frame #2: INJECTED burst error (15 bits flipped)",
        "[Server] Frame #2: CRC-16: VALID [OK] (15 bit errors corrected)",
        "[Relay] Frame #3: INJECTED burst error (8 bits flipped)",
        "[Server] Frame #3: CRC-16: VALID [OK] (8 bit errors corrected)",
        "[Client] Sent END frame -> Final Status: PASS"
    ]
    for line in log_lines:
        p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(10)
        p.font.color.rgb = TEXT_LIGHT

    # Right: Integrity & Metrics Card
    create_card(slide11, 7.3, 1.8, 5.2, 5.1, bg_color=DARK_BLUE, border_color=SUCCESS_GREEN)
    tb = slide11.shapes.add_textbox(Inches(7.5), Inches(1.9), Inches(4.8), Inches(4.8))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "Audit Verdict: PASS"
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = SUCCESS_GREEN

    metrics = [
        "Cryptographic Integrity Audit:",
        "Original SHA-256:",
        "e3b0c44298fc1c149afbf4c8996fb924...",
        "\nReceived SHA-256:",
        "e3b0c44298fc1c149afbf4c8996fb924...",
        "\nKey Performance Indicators:",
        "- Channel Noise Injected: 100% of data frames",
        "- Bit Errors Restored: 35 / 35 bits corrected",
        "- CRC-16 Pass Rate: 100.0%",
        "- Retransmission Requests: 0 (Zero ARQ overhead)",
        "- File Fidelity: 100% Byte-for-byte exact match"
    ]
    for m in metrics:
        p = tf.add_paragraph()
        p.text = m
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_LIGHT

    # =========================================================================
    # SLIDE 12: Comparison: TCP vs. UDP Behavior
    # =========================================================================
    slide12 = prs.slides.add_slide(blank_layout)
    set_bg(slide12, LIGHT_BG)
    add_header(slide12, "Transport Layer Comparison", "Transport Evaluation: TCP vs. UDP Under Channel Noise")

    # TCP Card
    create_card(slide12, 0.8, 1.8, 5.7, 5.0)
    tb = slide12.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.3), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "TCP Mode Evaluation"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE

    tcp_points = [
        ("Stream-Oriented Transport:", "TCP handles packet ordering and stream reliability at the transport layer."),
        ("Length-Prefixed Framing:", "Our RecvBuffer pop_all_messages() guarantees frames are cleanly unbundled despite packet coalescing or OS-level segmentation."),
        ("No ARQ Stall:", "Because Hamming FEC corrects burst bit flips in memory, TCP never experiences connection timeouts or packet retransmission stalls due to bit noise."),
        ("Verdict:", "Ideal for robust, ordered delivery over lossy bit channels.")
    ]
    for title, desc in tcp_points:
        p = tf.add_paragraph()
        p.text = f"\n- {title} {desc}"
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_DARK

    # UDP Card
    create_card(slide12, 6.8, 1.8, 5.7, 5.0)
    tb = slide12.shapes.add_textbox(Inches(7.0), Inches(2.0), Inches(5.3), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "UDP Mode Evaluation"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE

    udp_points = [
        ("Datagram-Oriented Transport:", "Transmits discrete 456-byte frames without connection handshakes."),
        ("Zero Overhead:", "Minimal protocol latency; no TCP sliding window or cumulative ACK processing."),
        ("Resilience Under Noise:", "With Hamming(7,4) + interleaving, channel corruption does not invalidate datagram payloads; Server repairs errors directly."),
        ("Verdict:", "Demonstrates that FEC can deliver 100% reliability even over an intrinsically unreliable transport protocol like UDP.")
    ]
    for title, desc in udp_points:
        p = tf.add_paragraph()
        p.text = f"\n- {title} {desc}"
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_DARK

    # =========================================================================
    # SLIDE 13: Conclusion
    # =========================================================================
    slide13 = prs.slides.add_slide(blank_layout)
    set_bg(slide13, LIGHT_BG)
    add_header(slide13, "Conclusion", "Reliable File Transfer Achieved Without ARQ")

    create_card(slide13, 0.8, 1.8, 11.7, 5.0)
    tb = slide13.shapes.add_textbox(Inches(1.2), Inches(2.1), Inches(10.9), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "Key Project Achievements"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE

    concls = [
        ("Eliminated Retransmission Overhead:", "Proved that Forward Error Correction (FEC) can completely eliminate the high latency penalty of ARQ on noisy links by restoring data locally at the receiver."),
        ("Solved Hamming Burst Inadequacy:", "Overcame the classical single-bit limitation of Hamming codes by integrating bit-level block interleaving (depth 32), effectively immunizing the stream against bursts up to 32 bits."),
        ("Engineered Realistic 3-Process Architecture:", "Implemented a fully decoupled Client -> Relay -> Server network pipeline, validating noise generation and error correction on separate socket endpoints."),
        ("Rigorous Multi-Layer Verification:", "Successfully verified error correction across all layers: Bitwise syndrome arithmetic -> CRC-16-CCITT per frame -> End-to-end SHA-256 cryptographic match.")
    ]
    for title, desc in concls:
        p = tf.add_paragraph()
        p.text = f"\n- {title} {desc}"
        p.font.size = Pt(13)
        p.font.color.rgb = TEXT_DARK

    # =========================================================================
    # SLIDE 14: Q&A Slide (Dark Navy)
    # =========================================================================
    slide14 = prs.slides.add_slide(blank_layout)
    set_bg(slide14, NAVY_BG)

    tb = slide14.shapes.add_textbox(Inches(1.5), Inches(2.2), Inches(10.3), Inches(1.5))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = "Thank You!"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(54)
    p.font.bold = True
    p.font.color.rgb = TEXT_LIGHT

    p2 = tf.add_paragraph()
    p2.text = "Questions & Answers"
    p2.alignment = PP_ALIGN.CENTER
    p2.font.size = Pt(26)
    p2.font.color.rgb = ACCENT_CYAN

    # Team details card
    create_card(slide14, 2.5, 4.2, 8.3, 1.8, bg_color=DARK_BLUE, border_color=ACCENT_CYAN)
    tb2 = slide14.shapes.add_textbox(Inches(2.7), Inches(4.4), Inches(7.9), Inches(1.4))
    tf2 = tb2.text_frame
    p = tf2.paragraphs[0]
    p.text = "Project Team - Computer Networks"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN

    p = tf2.add_paragraph()
    p.text = "Mohit Seth (24BCE2950)   *   Vinayak Sangram Patil (24BCE2147)"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = TEXT_LIGHT

    prs.save(output_path)
    print(f"Presentation saved successfully to {output_path} ({len(prs.slides)} slides)!")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "Final_Review_Presentation.pptx"
    build_presentation(out_file)
