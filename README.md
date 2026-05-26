# Steam Clip Importer / Steam 剪辑导入器

**English** | [中文](#中文)

Import any video into Steam Game Recording as a clip — one click.

---

## Features

- Select any video file, enter a Steam AppID, and add it to Steam Game Recording
- Automatic transcoding to Steam-compatible HEVC DASH format
- Video trimmed to clean 3-second segment boundaries for accurate progress bar
- Real-time progress bar with percentage display
- Safe gamerecording.pb update — original data is never corrupted

## Requirements

- Windows 10+
- **ffmpeg** / **ffprobe** installed and on system PATH
  - Download: https://ffmpeg.org/download.html

## Quick Start

1. Download `SteamClipImporter.exe` from [Releases](../../releases)
2. Double-click to launch
3. Select a video file
4. Enter the Steam AppID (e.g. CS2=730, Dota2=570)
5. Select your Steam recording folder (contains `gamerecording.pb` and `clips/`)
6. Click "开始导入" (Start Import)
7. Restart Steam to see the clip in Game Recording

## Build from Source

```bash
pip install -r requirements.txt
python main.py
```

## Package to .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "SteamClipImporter" --icon="app.ico" --add-data "app.ico;." main.py
```

Output: `dist/SteamClipImporter.exe`

## Project Structure

```
├── main.py          # tkinter GUI
├── importer.py      # Core import pipeline (transcode, DASH, metadata)
├── pb_utils.py      # Steam Protobuf encode/decode
├── requirements.txt # Python dependencies
└── app.ico          # App icon
```

## Steam AppID Reference

| Game | AppID |
|------|-------|
| CS2 | 730 |
| Dota 2 | 570 |
| Apex Legends | 1172470 |
| GTA V | 271590 |
| Elden Ring | 1245620 |
| PUBG | 578080 |

## How It Works

Steam Game Recording stores clips as:

```
clips/
  clip_<appid>_<timestamp>/
    clip.pb           # Protobuf metadata
    thumbnail.jpg     # Thumbnail
    timelines/        # Timeline JSON
    video/bg_xxx/     # DASH segments (HEVC + AAC)
      init-stream0.m4s
      chunk-stream0-00001.m4s
      ...
      session.mpd
gamerecording.pb      # Index file
```

This tool automates: video transcode → DASH segmentation → metadata generation → index update.

## Known Issues

- After playback ends, clicking play requires two clicks to restart (Steam client limitation for externally-added clips)

---

## 中文

将任意视频一键导入 Steam 游戏录制剪辑。

### 功能

- 选择任意视频文件，输入 Steam AppID，一键添加到 Steam 游戏录制
- 自动转码为 Steam 兼容的 HEVC DASH 格式
- 视频自动裁剪到 3 秒整倍数边界，确保进度条准确
- 实时进度条百分比显示
- gamerecording.pb 安全追加更新，不损坏原始数据

### 前提条件

- Windows 10+
- **ffmpeg** / **ffprobe** 已安装并添加到系统 PATH
  - 下载: https://ffmpeg.org/download.html

### 快速使用

1. 从 [Releases](../../releases) 下载 `SteamClipImporter.exe`
2. 双击运行
3. 选择视频文件
4. 填写 Steam AppID（如 CS2=730, Dota2=570）
5. 选择 Steam 录像文件夹（包含 `gamerecording.pb` 和 `clips/`）
6. 点击"开始导入"
7. 重启 Steam 客户端即可在游戏录制中播放

### 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 已知问题

- 播放结束后点击播放按钮需要点两次才能重新播放（Steam 客户端对外部剪辑的限制）
