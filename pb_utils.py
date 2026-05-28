"""Protobuf encoding utilities for Steam game recording files.

Handles low-level protobuf wire-format encoding and decoding for
clip.pb and gamerecording.pb files.
"""

import random
from datetime import datetime


# ---- Varint encoding ----

def decode_varint(data: bytes, pos: int):
    """Decode a protobuf varint from position, return (value, new_pos)."""
    result = 0; shift = 0
    while pos < len(data):
        byte = data[pos]; result |= (byte & 0x7f) << shift; pos += 1
        if not (byte & 0x80): return result, pos
        shift += 7
    return None, pos


def encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as a protobuf varint."""
    result = []
    while value > 0x7f:
        result.append((value & 0x7f) | 0x80)
        value >>= 7
    result.append(value & 0x7f)
    return bytes(result)



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


# ---- gamerecording.pb writer ----

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

    # --- 3. Append game entry if this appid has none ---
    has_entry = False
    pos = 0
    while pos < len(result):
        tag, pos2 = decode_varint(result, pos)
        fn = tag >> 3; wt = tag & 0x7
        if fn == 4 and wt == _WIRE_LENGTH_DELIMITED:
            length, pos3 = decode_varint(result, pos2)
            inner = result[pos3:pos3+length]
            ip = 0
            while ip < len(inner):
                itag, ip2 = decode_varint(inner, ip)
                ifn = itag >> 3; iwt = itag & 0x7
                if ifn == 1 and iwt == _WIRE_VARINT:
                    val, _ = decode_varint(inner, ip2)
                    if val == appid: has_entry = True
                    break
                ip = ip2
            if has_entry: break
        pos = pos2

    if not has_entry:
        gi = b''; gi += string_field(1, 'Recordings'); gi += string_field(2, 'General'); gi += varint_field(4, 100)
        tr = b''; tr += string_field(2, timeline_name); tr += varint_field(3, duration_ms)
        ge = b''; ge += varint_field(1, appid)
        ge += _tag(2, _WIRE_LENGTH_DELIMITED) + encode_varint(len(gi)) + gi
        ge += _tag(3, _WIRE_LENGTH_DELIMITED) + encode_varint(len(tr)) + tr
        result += _tag(4, _WIRE_LENGTH_DELIMITED) + encode_varint(len(ge)) + ge

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
