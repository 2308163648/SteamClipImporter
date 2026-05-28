"""Core import logic — converts any video into a Steam game-recording clip."""

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
# MPD builder
# ---------------------------------------------------------------------------

def _build_mpd(duration_s: float, seg_dur: float = 3.0, w: int = 1920, h: int = 1080) -> str:
    """Build a DASH MPD exactly matching native Steam format."""
    dur = f'{duration_s:.3f}'
    seg_us = int(seg_dur * 1_000_000)
    max_sd = f'PT{seg_dur:.1f}S'
    return (
        '﻿<?xml version="1.0" encoding="utf-8"?>\n'
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
        f' maxWidth="{w}" maxHeight="{h}">\n'
        '            <Representation id="0" mimeType="video/mp4"'
        ' codecs="hev1.2.4.L123.B0" bandwidth="12000000"'
        f' width="{w}" height="{h}">\n'
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
        '</MPD>\n'
    )

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _report(progress_cb, pct: float, status: str):
    if progress_cb:
        progress_cb(pct, status)


def _ffprobe_json(video_path: str):
    proc = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json',
         '-show_format', '-show_streams', video_path],
        capture_output=True, text=True, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f'无法解析视频文件: {video_path}\n{proc.stderr}')
    return json.loads(proc.stdout)


_RE_TIME1 = re.compile(r'time=(\d+):(\d+):(\d+\.?\d*)')
_RE_TIME2 = re.compile(r'time=(\d+\.?\d+)')

def _parse_ffmpeg_progress(line: str) -> Optional[float]:
    m = _RE_TIME1.search(line)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = _RE_TIME2.search(line)
    if m:
        return float(m.group(1))
    return None


# ---------------------------------------------------------------------------
# main pipeline
# ---------------------------------------------------------------------------

def import_video(
    video_path: str,
    appid: int,
    steam_folder: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> str:
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
    duration_ms = int(duration_s * 1000)

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

    out_w, out_h = 1920, 1080

    _report(progress_cb, 5, f'视频时长: {duration_s:.1f}s, {out_w}x{out_h}')

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
    _report(progress_cb, 12, '正在转码视频...')
    frag_tmp = os.path.join(video_dir, '_frag_temp.mp4')
    total_dur = duration_s
    last_pct = 15

    cmd1 = [
        'ffmpeg', '-y', '-i', video_path,
        '-c:v', 'libx265', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-x265-params', 'no-open-gop=1',
        '-vf', f'scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,'
               f'pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2,fps=60',
        '-force_key_frames', 'expr:gte(t,n_forced*3)',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
        '-f', 'mp4', frag_tmp,
    ]

    proc = subprocess.Popen(
        cmd1, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    )

    for line in proc.stderr:
        t = _parse_ffmpeg_progress(line)
        if t is not None and total_dur > 0:
            pct = 15 + (t / total_dur) * 57
            pct = min(pct, 72)
            if pct - last_pct >= 2:
                last_pct = pct
                _report(progress_cb, pct, f'正在转码视频... {t:.0f}s / {total_dur:.0f}s')

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError('视频转码失败')

    # pass 2 — DASH segments
    _report(progress_cb, 73, '正在生成 DASH 分段...')
    proc2 = subprocess.run(
        ['ffmpeg', '-y', '-i', frag_tmp, '-c', 'copy',
         '-f', 'dash', '-seg_duration', '3', '-use_template', '1', '-use_timeline', '0',
         '-init_seg_name', 'init-stream$RepresentationID$.m4s',
         '-media_seg_name', 'chunk-stream$RepresentationID$-$Number%05d$.m4s',
         'session.mpd'],
        capture_output=True, text=True, timeout=600, cwd=video_dir,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    )
    if proc2.returncode != 0:
        raise RuntimeError('DASH 分段生成失败')
    os.unlink(frag_tmp)

    # remove stray extra audio chunks
    for f in sorted(Path(video_dir).glob('chunk-stream1-*')):
        base = f.name.replace('chunk-stream1', 'chunk-stream0')
        if not (Path(video_dir) / base).exists():
            f.unlink()

    _report(progress_cb, 75, 'DASH 分段完成')

    # ---- step 4: thumbnail ----
    _report(progress_cb, 78, '正在生成缩略图...')
    subprocess.run(
        ['ffmpeg', '-y', '-i', video_path, '-ss', '00:00:01', '-vframes', '1', '-q:v', '2',
         '-vf', f'scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,'
                f'pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2',
         os.path.join(clip_dir, 'thumbnail.jpg')],
        capture_output=True, text=True, timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    )
    _report(progress_cb, 80, '缩略图已生成')

    # ---- step 5: metadata ----
    _report(progress_cb, 82, '正在创建元数据文件...')

    # timeline JSON
    tl_json = {
        'daterecorded': str(names['ts_unix']),
        'starttime': '0',
        'endtime': str(duration_ms),
    }
    with open(os.path.join(tl_dir, f'{names["timeline_name"]}.json'), 'w', encoding='utf-8') as f:
        json.dump(tl_json, f, indent='\t')

    # MPD — use the display duration (not padded) so progress bar is accurate
    with open(os.path.join(video_dir, 'session.mpd'), 'w', encoding='utf-8') as f:
        f.write(_build_mpd(duration_s, 3.0, out_w, out_h))

    # clip.pb
    clip_pb = build_clip_pb(
        appid=names['appid'],
        timeline_name=names['timeline_name'],
        bg_name=names['bg_name'],
        display_name=names['display_name'],
        ts_unix=names['ts_unix'],
        duration_ms=duration_ms,
        width=out_w,
        height=out_h,
    )
    with open(os.path.join(clip_dir, 'clip.pb'), 'wb') as f:
        f.write(clip_pb)

    _report(progress_cb, 90, '元数据文件已创建')

    # ---- step 6: update gamerecording.pb ----
    _report(progress_cb, 92, '正在更新索引文件...')
    from datetime import datetime as _dt
    shutil.copy2(gr_pb, f'{gr_pb}.{_dt.now().strftime("%Y%m%d_%H%M%S")}.bak')
    with open(gr_pb, 'rb') as f:
        gr_data = f.read()
    gr_data = update_gamerecording_pb(
        gr_data, names['appid'], names['timeline_name'],
        names['ts_unix'], duration_ms,
    )
    with open(gr_pb, 'wb') as f:
        f.write(gr_data)

    _report(progress_cb, 100, f'导入完成! {names["dir_name"]}')
    return clip_dir
