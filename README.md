# Steam Clip Importer

将任意视频一键导入 Steam 游戏录制剪辑中。

![screenshot](https://img.shields.io/badge/platform-Windows-blue)

## 功能

- 选择任意视频文件，输入 Steam AppID，一键添加到 Steam 游戏录制
- 自动转码为 Steam 兼容的 HEVC DASH 格式
- 保留原始画质（CRF 18, preset slow）
- 进度条实时显示导入进度

## 前提条件

- **ffmpeg** / **ffprobe** 已安装并添加到系统 PATH
  - 下载地址: https://ffmpeg.org/download.html
- Windows 10+

## 快速使用

1. 下载 `dist/SteamClipImporter.exe`（[Releases](../../releases) 页面）
2. 双击运行
3. 选择视频文件
4. 填写 Steam AppID（如 CS2=730, Dota2=570）
5. 选择 Steam 录像文件夹（包含 `gamerecording.pb` 和 `clips/` 目录）
6. 点击「开始导入」
7. 重启 Steam 客户端即可在游戏录制中播放

## 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "SteamClipImporter" --icon="app.ico" --add-data "app.ico;." main.py
```

输出在 `dist/SteamClipImporter.exe`。

## 项目结构

```
├── main.py          # tkinter GUI 界面
├── importer.py      # 核心导入管线（转码、DASH、元数据）
├── pb_utils.py      # Steam Protobuf 编解码
├── requirements.txt # Python 依赖
└── app.ico          # 应用图标
```

## Steam AppID 参考

| 游戏 | AppID |
|------|-------|
| CS2 | 730 |
| Dota 2 | 570 |
| Apex Legends | 1172470 |
| GTA V | 271590 |
| Elden Ring | 1245620 |
| PUBG | 578080 |

## 原理

Steam 游戏录制将剪辑存储为：

```
clips/
  clip_<appid>_<时间>/
    clip.pb           # Protobuf 元数据
    thumbnail.jpg     # 缩略图
    timelines/        # 时间线 JSON
    video/bg_xxx/     # DASH 视频分段 (HEVC + AAC)
      init-stream0.m4s
      chunk-stream0-00001.m4s
      ...
      session.mpd
gamerecording.pb      # 索引文件
```

本工具自动完成视频转码 → DASH 分段 → 元数据生成 → 索引更新全流程。
