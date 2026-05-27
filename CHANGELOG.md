# Changelog / 更新日志

---

## v1.1.0 (2026-05-27)

### Added / 新增
- Migrated from tkinter to PyQt5 with modern Fusion style / 从 tkinter 迁移到 PyQt5，使用 Fusion 现代风格
- White frosted glass background with rounded corners / 白色毛玻璃背景 + 圆角
- Resizable window with responsive layout / 窗口可自由缩放，布局自适应
- AppID input clear button (×) / AppID 输入框 × 清除按钮
- Auto-clear video path after import / 导入完成后自动清空视频路径
- Progress bar auto-reset after successful import / 导入成功后进度条自动归零
- Config persistence (last used folder remembered) / 配置持久化（记住上次选择的文件夹）
- Timestamped gamerecording.pb backups / gamerecording.pb 带时间戳备份

### Fixed / 修复
- MPD `maxSegmentDuration` format: `PT3S` → `PT3.0S` (caused loading issue) / MPD 格式修复，解决一直加载无法播放的问题
- Forced 60fps output for consistent DASH timing across source videos / 强制 60fps 输出，消除源视频帧率差异
- Closed GOP encoding (`no-open-gop=1`) for clean segment boundaries / 闭路 GOP 编码，分段边界干净
- Removed dead code from pb_utils.py (~120 lines of unused PbNode parser) / 移除 pb_utils.py 中未使用的解析器代码
- Config file now saved next to exe instead of temp directory / 配置文件保存到 exe 同目录

### Changed / 变更
- GUI framework: tkinter → PyQt5 (36MB exe) / GUI 框架改为 PyQt5
- Encoding: preset slow + CRF 18 + no-open-gop / 编码参数优化
- Resolution: always 1920×1080 / 分辨率统一 1920×1080
- Segment duration: fixed 3s standard DASH segments / 固定 3s 标准 DASH 分段

---

## v1.0.0 (2026-05-26)

### Added / 新增
- tkinter GUI with file picker, AppID input, and folder selector / tkinter 界面
- Automatic HEVC DASH transcoding with forced keyframes / 自动 HEVC DASH 转码
- clip.pb and gamerecording.pb metadata generation / 元数据生成
- Safe append-only gamerecording.pb update / 安全追加更新
- Custom app icon / 自定义图标

### Fixed / 修复
- DASH segment video/audio alignment / 分段对齐
- MPD format matching native Steam clips / MPD 格式匹配
- Timestamp computation / 时间戳计算

### Known Issues / 已知问题
- Replay requires two clicks after video ends / 播放结束后重播需要点两次
