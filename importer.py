"""Core import logic — converts any video into a Steam game-recording clip.

The public entry point is `import_video()`, which takes a progress callback
so the GUI can remain responsive.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from pb_utils import build_clip_pb, compute_names, update_gamerecording_pb

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

def _build_mpd(duration_s: float, seg_dur: int = 3) -> str:
    """Build a DASH MPD exactly matching native Steam format."""
    dur = f'{duration_s:.3f}'
    seg_us = seg_dur * 1_000_000
    max_sd = f'PT{seg_dur}.0S'
    return ('﻿<?xml version="1.0" encoding="utf-8"?>\n'
            '<MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' xmlns="urn:mpeg:dash:schema:mpd:2011"'
            ' xmlns:xlink="http://www.w3.org/1999/xlink"'
            ' xsi:schemaLocation="urn:mpeg:DASH:schema:MPD:2011'
            ' http://standards.iso.org/ittf/PubliclyAvailableStandards/MPEG-DASH_schema_files/DASH-MPD.xsd"'
            ' profiles="urn:mpeg:dash:profile:isoff-live:2011"'
            ' type="static" timeShiftBufferDepth="PT2H0M0.0S"'
            f' maxSegmentDuration="{max_sd}" minBufferTime="PT6.0S"'
            f' mediaPresentationDuration="PT{dur}S">\n'
            '    <Period id="0" start="PT0S">\n'
            '        <AdaptationSet id="0" contentType="video" startWithSAP="1"'
            ' segmentAlignment="true" bitstreamSwitching="true"'
            ' maxWidth="1920" maxHeight="1080">\n'
            '            <Representation id="0" mimeType="video/mp4"'
            ' codecs="hev1.2.4.L123.B0" bandwidth="12000000"'
            ' width="1920" height="1080">\n'
            f'                <SegmentTemplate timescale="1000000" duration="{seg_us}"'
            ' initialization="init-stream$RepresentationID$.m4s"'
            ' media="chunk-stream$RepresentationID$-$Number%05d$.m4s"'
            ' startNumber="1"/>\n'
            '            </Representation>\n'
            '        </AdaptationSet>\n'
            '        <AdaptationSet id="1" contentType="audio" startWithSAP="1"'
            ' segmentAlignment="true" bitstreamSwitching="true">\n'
            '            <Representation id="1" mimeType="audio/mp4"'
            ' codecs="mp4a.40.2" bandwidth="128000"'
            ' audioSamplingRate="48000">\n'
            '                <AudioChannelConfiguration'
            ' schemeIdUri="urn:mpeg:dash:23003:3:audio_channel_configuration:2011"'
            ' value="2"/>\n'
            f'                <SegmentTemplate timescale="1000000" duration="{seg_us}"'
            ' initialization="init-stream$RepresentationID$.m4s"'
            ' media="chunk-stream$RepresentationID$-$Number%05d$.m4s"'
            ' startNumber="1"/>\n'
            '            </Representation>\n'
            '        </AdaptationSet>\n'
            '    </Period>\n'
            '</MPD>\n')

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _report(progress_cb, pct: float, status: str):
    """Fire progress callback if one was provided."""
    if progress_cb:
        progress_cb(pct, status)


def _run(cmd: list, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a subprocess; raise on non-zero exit.  *cmd* is a list of strings."""
    # shell=True on Windows is needed for ffmpeg from PATH
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)


def _ffprobe_json(video_path: str):
    """Return parsed ffprobe JSON for *video_path*."""
    proc = _run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', video_path,
    ])
    return json.loads(proc.stdout)


def _parse_ffmpeg_progress(line: str) -> Optional[float]:
    """Extract time in seconds from an ffmpeg stderr line.  Returns None on miss."""
    m = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', line)
    if not m:
        m = re.search(r'time=(\d+\.?\d+)', line)
        if m:
            return float(m.group(1))
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mi * 60 + s


# ---------------------------------------------------------------------------
# main pipeline
# ---------------------------------------------------------------------------

def import_video(
    video_path: str,
    appid: int,
    steam_folder: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> str:
    """Import *video_path* into Steam game-recording clips.

    Parameters:
        video_path:   path to the source video file (any ffmpeg-supported format).
        appid:        Steam AppID for the game (e.g. 730 = CS2).
        steam_folder: folder that contains ``gamerecording.pb`` and ``clips/``.
        progress_cb:  optional callback ``(pct: float, status: str)``.

    Returns:
        The path to the newly created clip directory.
    """

    # ---- validate inputs ----
    _report(progress_cb, 0, '正在验证输入...')

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f'视频文件不存在: {video_path}')

    gr_pb = os.path.join(steam_folder, 'gamerecording.pb')
    clips_dir = os.path.join(steam_folder, 'clips')
    if not os.path.isfile(gr_pb):
        raise FileNotFoundError(f'未找到 gamerecording.pb: {gr_pb}')
    if not os.path.isdir(clips_dir):
        raise FileNotFoundError(f'未找到 clips 目录: {clips_dir}')

    # ---- step 1: probe ----
    _report(progress_cb, 2, '正在解析视频信息...')
    info = _ffprobe_json(video_path)

    duration_s = float(info['format']['duration'])

    # trim to nearest 3s boundary so all DASH segments are full
    import math
    trimmed_dur = math.floor(duration_s / 3.0) * 3
    # only trim if it loses < 1s or < 10% of duration
    if trimmed_dur < 1 or (duration_s - trimmed_dur) > max(1.0, duration_s * 0.1):
        trimmed_dur = duration_s
    trim_flag = ['-t', str(trimmed_dur)] if trimmed_dur < duration_s - 0.1 else []

    duration_ms = int(trimmed_dur * 1000)

    # pick first video / audio streams
    video_stream = audio_stream = None
    for st in info['streams']:
        if st['codec_type'] == 'video' and video_stream is None:
            video_stream = st
        elif st['codec_type'] == 'audio' and audio_stream is None:
            audio_stream = st

    if video_stream is None:
        raise ValueError('视频文件中没有视频流')
    if audio_stream is None:
        raise ValueError('视频文件中没有音频流')

    if trim_flag:
        _report(progress_cb, 5, f'视频时长: {duration_s:.1f}s → 裁剪至 {trimmed_dur:.0f}s, '
                 f'{video_stream.get("width")}x{video_stream.get("height")}')
    else:
        _report(progress_cb, 5, f'视频时长: {duration_s:.1f}s, '
                 f'{video_stream.get("width")}x{video_stream.get("height")}')

    # ---- step 2: create directory structure ----
    _report(progress_cb, 8, '正在创建目录...')
    names = compute_names(appid)
    clip_dir = os.path.join(clips_dir, names['dir_name'])
    video_dir = os.path.join(clip_dir, 'video', names['bg_name'])
    tl_dir = os.path.join(clip_dir, 'timelines')
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(tl_dir, exist_ok=True)

    _report(progress_cb, 10, f'目录: {names["dir_name"]}')

    # ---- step 3: transcode + DASH ----
    _report(progress_cb, 12, '正在转码视频 (HEVC 1080p)...')

    frag_tmp = os.path.join(video_dir, '_frag_temp.mp4')
    total_dur = trimmed_dur
    last_pct = 15

    # pass 1 — fragmented MP4 (15 % → 72 %)
    cmd1 = [
        'ffmpeg', '-y', '-i', video_path,
        *trim_flag,
        '-c:v', 'libx265', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
        '-force_key_frames', 'expr:gte(t,n_forced*3)',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
        '-f', 'mp4', frag_tmp,
    ]
    proc = subprocess.Popen(
        cmd1, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    )

    # read progress from stderr
    for line in proc.stderr:
        t = _parse_ffmpeg_progress(line)
        if t is not None and total_dur > 0:
            pct = 15 + (t / total_dur) * 57  # 15 → 72
            pct = min(pct, 72)
            if pct - last_pct >= 2:  # update every 2 %
                last_pct = pct
                _report(progress_cb, pct, f'正在转码视频... {t:.0f}s / {total_dur:.1f}s')

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError('视频转码失败')

    # pass 2 — DASH segments (72 % → 75 %)
    _report(progress_cb, 73, '正在生成 DASH 分段...')
    cmd2 = [
        'ffmpeg', '-y', '-i', frag_tmp, '-c', 'copy',
        '-f', 'dash', '-seg_duration', '3', '-use_template', '1', '-use_timeline', '0',
        '-init_seg_name', 'init-stream$RepresentationID$.m4s',
        '-media_seg_name', 'chunk-stream$RepresentationID$-$Number%05d$.m4s',
        'session.mpd',
    ]
    proc2 = subprocess.run(
        cmd2, capture_output=True, text=True, timeout=600, cwd=video_dir,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    )
    if proc2.returncode != 0:
        raise RuntimeError('DASH 分段生成失败')

    # clean up temp file
    os.unlink(frag_tmp)

    # remove stray extra audio chunk (happens due to AAC frame padding)
    for f in sorted(Path(video_dir).glob('chunk-stream1-*')):
        base = f.name.replace('chunk-stream1', 'chunk-stream0')
        if not (Path(video_dir) / base).exists():
            f.unlink()

    _report(progress_cb, 75, 'DASH 分段完成')

    # ---- step 4: thumbnail ----
    _report(progress_cb, 78, '正在生成缩略图...')
    thumb_path = os.path.join(clip_dir, 'thumbnail.jpg')
    _run([
        'ffmpeg', '-y', '-i', video_path, '-ss', '00:00:01', '-vframes', '1', '-q:v', '2',
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
        thumb_path,
    ])
    _report(progress_cb, 80, '缩略图已生成')

    # ---- step 5: metadata files ----
    _report(progress_cb, 82, '正在创建元数据文件...')

    # 5a. timeline JSON
    tl_json = {
        'daterecorded': str(names['ts_unix']),
        'starttime': '0',
        'endtime': str(duration_ms),
    }
    tl_path = os.path.join(tl_dir, f'{names["timeline_name"]}.json')
    with open(tl_path, 'w', encoding='utf-8') as f:
        json.dump(tl_json, f, indent='\t')

    # 5b. session.mpd — use padded duration for clean segment alignment
    mpd_path = os.path.join(video_dir, 'session.mpd')
    with open(mpd_path, 'w', encoding='utf-8') as f:
        f.write(_build_mpd(trimmed_dur))

    # 5c. clip.pb
    clip_pb = build_clip_pb(
        appid=names['appid'],
        timeline_name=names['timeline_name'],
        bg_name=names['bg_name'],
        display_name=names['display_name'],
        ts_unix=names['ts_unix'],
        duration_ms=duration_ms,
    )
    with open(os.path.join(clip_dir, 'clip.pb'), 'wb') as f:
        f.write(clip_pb)

    _report(progress_cb, 90, '元数据文件已创建')

    # ---- step 6: update gamerecording.pb ----
    _report(progress_cb, 92, '正在更新索引文件...')

    # backup
    shutil.copy2(gr_pb, gr_pb + '.bak')

    with open(gr_pb, 'rb') as f:
        gr_data = f.read()

    gr_data = update_gamerecording_pb(
        gr_data, names['appid'], names['timeline_name'],
        names['ts_unix'], duration_ms,
    )

    with open(gr_pb, 'wb') as f:
        f.write(gr_data)

    _report(progress_cb, 98, '索引文件已更新')

    # ---- done ----
    _report(progress_cb, 100, f'导入完成! {names["dir_name"]}')

    return clip_dir
