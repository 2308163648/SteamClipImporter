# Changelog

## v1.0.0 (2026-05-26)

### Added
- tkinter GUI with file picker, AppID input, and folder selector
- Automatic HEVC DASH transcoding with forced keyframes at 3s boundaries
- Video trimming to nearest 3s boundary for clean segment alignment
- Canvas-based progress bar with percentage display
- clip.pb and gamerecording.pb metadata generation
- Safe append-only gamerecording.pb update (no data corruption)
- Custom app icon support
- ffmpeg/ffprobe availability check on startup

### Fixed
- DASH segment video/audio alignment (forced keyframes)
- MPD format matching native Steam clips (BOM, single-line attributes, exact codec)
- Progress bar accuracy (trim video to clean 3s segment boundaries)
- gamerecording.pb corruption risk (append-only strategy)
- Timestamp computation (correct UTC/local time handling)
- GUI layout alignment (AppID and folder inputs in same grid row)

### Known Issues
- Replay requires two clicks after video ends (Steam client limitation for external clips)
