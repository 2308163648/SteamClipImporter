# Changelog / 更新日志

---

## v1.2.0 (2026-05-28)

### Fixed / 修复
- All 25 game names verified against Steam API (8+ were incorrect) / 通过 Steam API 验证全部 25 个游戏名称（8 个有误）
- 2669320 corrected from "Delta Force" to "EA SPORTS FC 25" / 2669320 更正
- Game names unified to English / 游戏名统一为英语

### Changed / 优化
- Precompiled regex for ffmpeg progress parsing / 预编译正则表达式提升解析效率
- Removed unused imports / 移除无用导入

---

## v1.1.0 (2026-05-27)

### Added / 新增
- PyQt5 GUI (migrated from tkinter) with modern Fusion style / PyQt5 现代界面
- Language toggle (Chinese / English) with persistence / 中英文切换，偏好保存
- Auto game name recognition (built-in 25 games + Steam API lookup) / 自动识别游戏名称（内置 25 款 + Steam API 查询）
- Debounce timer for AppID input (400ms, no lag) / AppID 输入防抖
- AppID clear button (×) / AppID 清除按钮
- Resizable window with responsive layout / 窗口可缩放，布局自适应
- Config persistence (last folder remembered) / 配置持久化
- Auto-clear video path after import / 导入后自动清空视频路径
- Progress bar resets after import / 进度条导入后归零
- Timestamped gamerecording.pb backups / gamerecording.pb 带时间戳备份
- Game entry auto-creation for new AppIDs / 新 AppID 自动创建 game entry
- Async game name lookup via QThread / 异步线程查询游戏名

### Fixed / 修复
- MPD `maxSegmentDuration` format: `PT3S` → `PT3.0S` (caused infinite loading) / MPD 格式修复
- Forced 60fps output for consistent DASH timing / 强制 60fps
- Closed GOP encoding (`no-open-gop=1`) / 闭路 GOP 编码
- Signal disconnect crash in game name lookup / 信号断开崩溃修复
- Removed dead code from pb_utils.py (~120 lines) / 移除 120 行死代码
- Config file saved next to exe instead of temp directory / 配置文件路径修复

### Changed / 变更
- Encoding: preset slow + CRF 18 + no-open-gop / 编码参数优化
- Resolution: always 1920×1080 / 分辨率统一
- Segment duration: fixed 3s standard DASH segments / 固定 3s 分段

---

## v1.0.0 (2026-05-26)

### Added / 新增
- tkinter GUI with file picker, AppID input, and folder selector
- Automatic HEVC DASH transcoding with forced keyframes at 3s boundaries
- clip.pb and gamerecording.pb metadata generation
- Safe append-only gamerecording.pb update
- Custom app icon

### Fixed / 修复
- DASH segment video/audio alignment
- MPD format matching native Steam clips
- Timestamp computation (correct UTC/local time handling)

### Known Issues / 已知问题
- Replay requires two clicks after video ends (Steam limitation) / 重播需点两次
