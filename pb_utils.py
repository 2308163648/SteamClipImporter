"""Protobuf encoding utilities for Steam game recording files.

Handles low-level protobuf wire-format encoding and decoding for
clip.pb and gamerecording.pb files.
"""

import struct
import random
from datetime import datetime


# ---- Varint encoding ----

def encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as a protobuf varint."""
    result = []
    while value > 0x7f:
        result.append((value & 0x7f) | 0x80)
        value >>= 7
    result.append(value & 0x7f)
    return bytes(result)


def decode_varint(data: bytes, pos: int):
    """Decode a protobuf varint from position, return (value, new_pos)."""
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7f) << shift
        pos += 1
        if not (byte & 0x80):
            return result, pos
        shift += 7
    return None, pos


# ---- Field encoding helpers ----

_WIRE_VARINT = 0
_WIRE_LENGTH_DELIMITED = 2


def _tag(field_number: int, wire_type: int) -> bytes:
    return encode_varint((field_number << 3) | wire_type)


def varint_field(field_number: int, value: int) -> bytes:
    return _tag(field_number, _WIRE_VARINT) + encode_varint(value)


def bytes_field(field_number: int, data: bytes) -> bytes:
    return _tag(field_number, _WIRE_LENGTH_DELIMITED) + encode_varint(len(data)) + data


def string_field(field_number: int, text: str) -> bytes:
    return bytes_field(field_number, text.encode('utf-8'))


def embedded_field(field_number: int, msg: bytes) -> bytes:
    return bytes_field(field_number, msg)


# ---- clip.pb builder ----

def build_clip_pb(
    appid: int,
    timeline_name: str,
    bg_name: str,
    display_name: str,
    ts_unix: int,
    duration_ms: int,
    width: int = 1920,
    height: int = 1080,
) -> bytes:
    """Build a complete clip.pb protobuf message.

    Args:
        appid: Steam AppID (e.g. 730 for CS2)
        timeline_name: e.g. 'timeline_730260526_082232'
        bg_name: e.g. 'bg_730_20260526_082232'
        display_name: e.g. 'CS2 - 2026-05-26 16:22:32'
        ts_unix: Unix timestamp for daterecorded
        duration_ms: Video duration in milliseconds
        width: Video width in pixels
        height: Video height in pixels
    """
    # Embedded BgInfo message
    bg_info = b''
    bg_info += string_field(1, bg_name)
    bg_info += varint_field(2, 0)           # start offset
    bg_info += varint_field(3, duration_ms)  # endtime ms
    bg_info += varint_field(4, 4)            # codec flag (always 4)
    bg_info += varint_field(10, 0)           # unknown

    # Embedded ClipInfo message
    clip_info = b''
    clip_info += string_field(1, timeline_name)
    clip_info += varint_field(2, appid)
    clip_info += varint_field(3, ts_unix)    # daterecorded
    clip_info += varint_field(4, duration_ms) # endtime ms
    clip_info += embedded_field(5, bg_info)

    # Top-level ClipFile message
    clip_pb = b''
    clip_pb += embedded_field(1, clip_info)
    clip_pb += varint_field(2, 0)            # clip offset (always 0)
    clip_pb += varint_field(3, ts_unix)
    clip_pb += varint_field(4, appid)
    clip_pb += varint_field(6, random.randint(10000000, 99999999))
    clip_pb += string_field(7, display_name)
    clip_pb += varint_field(8, 0)
    clip_pb += varint_field(12, width)
    clip_pb += varint_field(13, height)

    return clip_pb


# ---- gamerecording.pb reader / writer ----

class PbNode:
    """A parsed protobuf field node, supporting tree traversal."""
    def __init__(self, field_number, wire_type, value=None, children=None):
        self.field_number = field_number
        self.wire_type = wire_type
        self.value = value        # for varint or raw bytes
        self.children = children or []  # for embedded messages

    def serialize(self) -> bytes:
        if self.wire_type == _WIRE_VARINT:
            return _tag(self.field_number, _WIRE_VARINT) + encode_varint(self.value or 0)
        elif self.wire_type == _WIRE_LENGTH_DELIMITED:
            if self.children:
                inner = b''.join(c.serialize() for c in self.children)
            elif isinstance(self.value, bytes):
                inner = self.value
            elif isinstance(self.value, str):
                inner = self.value.encode('utf-8')
            else:
                inner = b''
            return _tag(self.field_number, _WIRE_LENGTH_DELIMITED) + encode_varint(len(inner)) + inner
        elif self.wire_type == 5:  # fixed32
            return _tag(self.field_number, 5) + struct.pack('<I', self.value or 0)
        elif self.wire_type == 1:  # fixed64
            return _tag(self.field_number, 1) + struct.pack('<Q', self.value or 0)
        else:
            raise ValueError(f"Unsupported wire type: {self.wire_type}")


def parse_protobuf(data: bytes, pos: int = 0, max_depth: int = 100) -> list:
    """Parse raw protobuf bytes into a list of PbNode objects."""
    nodes = []
    while pos < len(data):
        tag, pos = decode_varint(data, pos)
        field_number = tag >> 3
        wire_type = tag & 0x7

        if wire_type == _WIRE_VARINT:
            value, pos = decode_varint(data, pos)
            nodes.append(PbNode(field_number, wire_type, value=value))
        elif wire_type == _WIRE_LENGTH_DELIMITED:
            length, pos = decode_varint(data, pos)
            raw = data[pos:pos + length]
            pos += length
            if max_depth > 0:
                try:
                    children = parse_protobuf(raw, 0, max_depth - 1)
                    if children:
                        nodes.append(PbNode(field_number, wire_type, children=children))
                        continue
                except Exception:
                    pass
            nodes.append(PbNode(field_number, wire_type, value=raw))
        elif wire_type == 5:  # fixed32
            value = struct.unpack('<I', data[pos:pos + 4])[0]
            pos += 4
            nodes.append(PbNode(field_number, wire_type, value=value))
        elif wire_type == 1:  # fixed64
            value = struct.unpack('<Q', data[pos:pos + 8])[0]
            pos += 8
            nodes.append(PbNode(field_number, wire_type, value=value))
    return nodes


def find_child(node: PbNode, field_number: int):
    """Find the first direct child with the given field number."""
    for child in node.children:
        if child.field_number == field_number:
            return child
    return None


def find_children(node: PbNode, field_number: int) -> list:
    """Find all direct children with the given field number."""
    return [c for c in node.children if c.field_number == field_number]


def get_string(node: PbNode) -> str:
    """Get a string value from a PbNode, decoding if necessary."""
    if node is None:
        return None
    if isinstance(node.value, bytes):
        try:
            return node.value.decode('utf-8')
        except Exception:
            return None
    return str(node.value) if node.value is not None else None


def update_gamerecording_pb(data: bytes, appid: int, timeline_name: str, ts_unix: int, duration_ms: int) -> bytes:
    """Add a new clip to gamerecording.pb by appending new entries.

    This uses a safe *append-only* strategy for field 1 and field 2 —
    the original bytes are never parsed & re-serialised, so we cannot
    corrupt existing data.

    For field-4 (game entries) we do an in-place insertion into the
    first matching game entry, which is a targeted edit.

    Returns the updated protobuf bytes.
    """
    result = bytearray(data)

    # --- 1. Timeline entry (append field 1) ---
    tl_inner = b''
    tl_inner += string_field(1, timeline_name)
    tl_inner += varint_field(2, appid)
    tl_inner += varint_field(3, ts_unix)
    tl_inner += varint_field(4, duration_ms)

    result += _tag(1, _WIRE_LENGTH_DELIMITED) + encode_varint(len(tl_inner)) + tl_inner

    # --- 2. Session / recent clip entry (append field 2) ---
    clip_inner = b''
    clip_inner += varint_field(1, appid)
    clip_inner += varint_field(2, ts_unix)
    clip_inner += varint_field(3, 2)                # type: clip
    clip_inner += string_field(4, timeline_name)
    clip_inner += varint_field(5, 0)
    clip_inner += varint_field(6, duration_ms)
    clip_inner += varint_field(7, 12000)            # bitrate hint
    clip_inner += string_field(8, '')
    clip_inner += string_field(9, '')
    clip_inner += varint_field(10, 0)

    session_inner = b''
    session_inner += varint_field(1, appid)
    session_inner += _tag(2, _WIRE_LENGTH_DELIMITED) + encode_varint(len(clip_inner)) + clip_inner

    result += _tag(2, _WIRE_LENGTH_DELIMITED) + encode_varint(len(session_inner)) + session_inner

    return bytes(result)


# ---- Name helpers ----

def compute_names(appid: int):
    """Compute all naming components for a new clip.

    Uses current time. Returns a dict with all names and timestamps.
    """
    now = datetime.now()
    utc_now = datetime.utcnow()
    ts_unix = int(now.timestamp())

    return {
        'appid': appid,
        'ts_unix': ts_unix,
        'dir_name': f'clip_{appid}_{now.strftime("%Y%m%d_%H%M%S")}',
        'timeline_name': f'timeline_{appid}{utc_now.strftime("%y%m%d_%H%M%S")}',
        'bg_name': f'bg_{appid}_{utc_now.strftime("%Y%m%d_%H%M%S")}',
        'display_name': f'Game {appid} - {now.strftime("%Y-%m-%d %H:%M:%S")}',
    }
