"""
Transport Buffer Layer - Handles TCP byte-stream and UDP datagram framing.

TCP: RecvBuffer class accumulates raw bytes and pops off complete 
     [4-byte length][payload] messages as they become fully available.
     Since recv() can return partial or coalesced data, this buffer
     handles reassembly.

UDP: Each sendto/recvfrom is one full datagram already, but we still
     use the same length-prefix format for symmetry.
"""

import struct
from typing import Optional, Tuple


class RecvBuffer:
    """
    Receive buffer for TCP connections.
    Handles partial reads and message coalescing via length-prefixed framing.
    
    Message format: [4-byte big-endian length][payload]
    """
    
    def __init__(self):
        self.buffer = bytearray()
    
    def add_data(self, data: bytes):
        """Add received data to the buffer."""
        self.buffer.extend(data)
    
    def try_pop_message(self) -> Optional[bytes]:
        """
        Try to extract a complete message from the buffer.
        Returns message payload if available, None otherwise.
        """
        if len(self.buffer) < 4:
            return None
        
        msg_len = struct.unpack('>I', self.buffer[:4])[0]
        
        if len(self.buffer) < 4 + msg_len:
            return None
        
        payload = bytes(self.buffer[4:4 + msg_len])
        del self.buffer[:4 + msg_len]
        return payload
    
    def pop_all_messages(self):
        """Extract all complete messages from the buffer."""
        messages = []
        while True:
            msg = self.try_pop_message()
            if msg is None:
                break
            messages.append(msg)
        return messages
    
    def __len__(self):
        return len(self.buffer)


def wrap_message(payload: bytes) -> bytes:
    """
    Wrap a payload with a 4-byte length prefix.
    Format: [4-byte big-endian length][payload]
    """
    length = len(payload)
    return struct.pack('>I', length) + payload


def unwrap_message(data: bytes) -> bytes:
    """
    Unwrap a length-prefixed message.
    Returns the payload (without the 4-byte length header).
    """
    if len(data) < 4:
        raise ValueError(f"Data too short: {len(data)} bytes")
    
    length = struct.unpack('>I', data[:4])[0]
    if len(data) < 4 + length:
        raise ValueError(f"Data too short for payload: expected {4 + length}, got {len(data)}")
    
    return data[4:4 + length]


def protocol_test():
    """Test TCP receive buffer and message wrapping."""
    print("Running protocol layer test...")
    
    original = b"Hello, Computer Networks!"
    wrapped = wrap_message(original)
    unwrapped = unwrap_message(wrapped)
    assert unwrapped == original
    print(f"  [PASS] Message wrap/unwrap: {len(original)} bytes")
    
    buf = RecvBuffer()
    buf.add_data(wrapped[:3])
    msg = buf.try_pop_message()
    assert msg is None
    print(f"  [PASS] Partial header: handled correctly")
    
    buf.add_data(wrapped[3:])
    msg = buf.try_pop_message()
    assert msg == original
    print(f"  [PASS] Complete message extracted")
    
    buf2 = RecvBuffer()
    msg1 = b"First message"
    msg2 = b"Second message"
    wrapped1 = wrap_message(msg1)
    wrapped2 = wrap_message(msg2)
    buf2.add_data(wrapped1 + wrapped2)
    messages = buf2.pop_all_messages()
    assert len(messages) == 2
    assert messages[0] == msg1
    assert messages[1] == msg2
    print(f"  [PASS] Coalesced messages: extracted {len(messages)} messages")
    print("\n  [PASS] All protocol tests passed!")


if __name__ == "__main__":
    protocol_test()
