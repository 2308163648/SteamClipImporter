"""Steam Clip Importer — PyQt5 GUI with i18n."""
import json, os, shutil, sys, urllib.request
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon
from importer import import_video

# ── i18n ────────────────────────────────────────────────────────────────
LANG = 'zh'
T = {
    'title':          {'zh': 'Steam 剪辑导入器',   'en': 'Steam Clip Importer'},
    'video_file':     {'zh': '视频文件',           'en': 'Video File'},
    'browse':         {'zh': '浏览',              'en': 'Browse'},
    'browse_video':   {'zh': '选择视频文件',        'en': 'Select Video File'},
    'placeholder_vid':{'zh': '选择视频文件...',      'en': 'Select video file...'},
    'steam_appid':    {'zh': 'Steam AppID',       'en': 'Steam AppID'},
    'appid_hint':     {'zh': '举例：CS2=730, Dota2=570', 'en': 'e.g. CS2=730, Dota2=570'},
    'steam_folder':   {'zh': 'Steam 录像文件夹',    'en': 'Steam Recording Folder'},
    'placeholder_dir':{'zh': '选择包含 gamerecording.pb 的文件夹...', 'en': 'Folder with gamerecording.pb...'},
    'progress':       {'zh': '导入进度',           'en': 'Import Progress'},
    'ready':          {'zh': '就绪',              'en': 'Ready'},
    'start_import':   {'zh': '开始导入',           'en': 'Start Import'},
    'importing':      {'zh': '处理中...',          'en': 'Processing...'},
    'starting':       {'zh': '正在启动...',        'en': 'Starting...'},
    'success':        {'zh': '导入成功',           'en': 'Import Successful'},
    'success_msg':    {'zh': '剪辑已成功导入!',     'en': 'Clip imported successfully!'},
    'failed':         {'zh': '导入失败',           'en': 'Import Failed'},
    'error':          {'zh': '错误',              'en': 'Error'},
    'err_no_video':   {'zh': '请选择有效的视频文件',  'en': 'Please select a valid video file'},
    'err_appid':      {'zh': 'AppID 必须是一个有效的数字', 'en': 'AppID must be a valid number'},
    'err_no_dir':     {'zh': '请选择有效的 Steam 录像文件夹', 'en': 'Select a valid Steam recording folder'},
    'err_no_pb':      {'zh': '未找到 gamerecording.pb', 'en': 'gamerecording.pb not found'},
    'err_ffmpeg_title':{'zh': '缺少依赖',          'en': 'Missing Dependency'},
    'err_ffmpeg':     {'zh': '未找到 ffmpeg / ffprobe。\n请安装并添加到 PATH。\nhttps://ffmpeg.org/download.html',
                       'en': 'ffmpeg/ffprobe not found.\nInstall and add to PATH.\nhttps://ffmpeg.org/download.html'},
    'lang_btn':       {'zh': 'EN',               'en': '中文'},
    'video_filter':   {'zh': '视频文件 (*.mp4 *.mkv *.mov *.avi *.webm);;所有文件 (*.*)',
                       'en': 'Video Files (*.mp4 *.mkv *.mov *.avi *.webm);;All Files (*.*)'},
}
def t(key): return T.get(key, {}).get(LANG, key)

# ── config ──────────────────────────────────────────────────────────────
def _cfg_path():
    if getattr(sys, 'frozen', False): base = os.path.dirname(sys.executable)
    else: base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'SteamClipImporter.json')
def _load_cfg():
    try:
        with open(_cfg_path(),'r',encoding='utf-8') as f: return json.load(f)
    except: return {}
def _save_cfg(cfg):
    with open(_cfg_path(),'w',encoding='utf-8') as f: json.dump(cfg,f,ensure_ascii=False,indent=2)
def _check_ffmpeg():
    return shutil.which('ffmpeg') and shutil.which('ffprobe')

# ── game name lookup (async) ────────────────────────────────────────────
GAME_NAMES = {
    730:'Counter-Strike 2', 570:'Dota 2', 578080:'PUBG: BATTLEGROUNDS',
    1172470:'Apex Legends', 271590:'Grand Theft Auto V', 1245620:'ELDEN RING',
    292030:'The Witcher 3: Wild Hunt', 582010:'Monster Hunter: World',
    814380:'Sekiro: Shadows Die Twice', 1085660:'Destiny 2', 252490:'Rust',
    440:'Team Fortress 2', 550:'Left 4 Dead 2', 620:'Portal 2',
    1446780:'MONSTER HUNTER RISE', 268910:'Cuphead',
    2622380:'ELDEN RING NIGHTREIGN', 264710:'Subnautica',
    2050650:'Resident Evil 4', 2669320:'EA SPORTS FC 25',
    1771300:'Kingdom Come: Deliverance II', 2322050:'BIKEOUT',
    1030300:'Hollow Knight: Silksong', 2420510:'HoloCure',
    2526380:'Sword of Convallaria',
}
_cache = dict(GAME_NAMES)

class NameLookup(QThread):
    done = pyqtSignal(int, str)
    def __init__(self, appid): super().__init__(); self.aid = appid
    def run(self):
        try:
            url = f'https://store.steampowered.com/api/appdetails?appids={self.aid}'
            req = urllib.request.Request(url, headers={'User-Agent':'SteamClipImporter/1.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                app_data = data.get(str(self.aid), {})
                if app_data.get('success') and app_data.get('data',{}).get('type') == 'game':
                    n = app_data['data'].get('name', '')
                    if n: _cache[self.aid] = n; self.done.emit(self.aid, n)
        except: pass

# ── import worker ───────────────────────────────────────────────────────
class ImportWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    def __init__(self, video, appid, folder):
        super().__init__(); self.v=video; self.a=appid; self.f=folder
    def run(self):
        try:
            r = import_video(self.v, self.a, self.f, progress_cb=lambda p,s: self.progress.emit(int(p),s))
            self.finished.emit(True, r)
        except Exception as e: self.finished.emit(False, str(e))

# ── main window ─────────────────────────────────────────────────────────
ACCENT = '#2563eb'; SUB = '#94a3b8'; FG = '#1e293b'; CARD = '#f8fafc'; BORDER = '#e2e8f0'

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        global LANG
        self._cfg = _load_cfg(); LANG = self._cfg.get('lang','zh'); LANG = LANG if LANG in ('zh','en') else 'zh'
        self.setWindowTitle(t('title'))
        self.setMinimumSize(520, 360); self.resize(580, 400)
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.ico')
        if os.path.exists(ico): self.setWindowIcon(QIcon(ico))
        self._worker = None; self._lu = None; self._build(); self._centre()

    def _centre(self):
        s = QApplication.primaryScreen().availableGeometry()
        self.move((s.width()-self.width())//2, (s.height()-self.height())//2)

    def closeEvent(self, ev):
        if self._lu and self._lu.isRunning(): self._lu.quit(); self._lu.wait(200)
        if self._worker and self._worker.isRunning(): self._worker.quit(); self._worker.wait(200)
        super().closeEvent(ev)

    def _build(self):
        self.setStyleSheet(f"""
            QWidget{{background:#fff;color:{FG};font-family:'Microsoft YaHei UI';font-size:13px;}}
            QLineEdit{{background:{CARD};border:1px solid {BORDER};border-radius:4px;padding:6px 8px;font-size:13px;}}
            QLineEdit:focus{{border-color:{ACCENT};}}
            QPushButton{{border:1px solid {BORDER};border-radius:4px;padding:6px 14px;background:#fff;font-size:13px;}}
            QPushButton:hover{{background:#f1f5f9;}}
            QPushButton#btnImport{{background:{ACCENT};color:#fff;border:none;font-size:15px;font-weight:bold;padding:10px 0;border-radius:6px;}}
            QPushButton#btnImport:hover{{background:#1d4ed8;}}
            QPushButton#btnImport:disabled{{background:#94a3b8;}}
            QPushButton#btnLang{{background:transparent;border:1px solid {BORDER};font-size:11px;padding:2px 8px;}}
            QProgressBar{{border:none;background:{BORDER};border-radius:4px;height:18px;}}
            QProgressBar::chunk{{background:{ACCENT};border-radius:4px;}}
            QLabel#pctLabel{{font-size:22px;font-weight:bold;color:{ACCENT};}}
            QLabel#statusLabel{{color:{SUB};font-size:12px;}}
            QLabel#hintLabel{{color:{SUB};font-size:11px;}}
            QLabel#titleLabel{{font-size:18px;font-weight:bold;}}
            QLabel#gameLabel{{color:{ACCENT};font-size:11px;font-weight:bold;}}
        """)
        ly = QVBoxLayout(self); ly.setContentsMargins(24,18,24,18); ly.setSpacing(0)

        # title + lang toggle
        tr = QHBoxLayout(); tr.setSpacing(8)
        self.lbl_title = QLabel(t('title')); self.lbl_title.setObjectName('titleLabel')
        tr.addWidget(self.lbl_title); tr.addStretch()
        self.btn_lang = QPushButton(t('lang_btn')); self.btn_lang.setObjectName('btnLang')
        self.btn_lang.setFixedSize(44,24); self.btn_lang.clicked.connect(self._toggle_lang)
        tr.addWidget(self.btn_lang); ly.addLayout(tr); ly.addSpacing(12)

        # video
        self.lbl_vid = QLabel(t('video_file')); ly.addWidget(self.lbl_vid)
        vr = QHBoxLayout(); vr.setSpacing(8)
        self.le_video = QLineEdit(); self.le_video.setPlaceholderText(t('placeholder_vid'))
        vr.addWidget(self.le_video)
        self.btn_vid = QPushButton(t('browse')); self.btn_vid.setStyleSheet('padding:6px 10px;'); self.btn_vid.clicked.connect(self._browse_video)
        vr.addWidget(self.btn_vid); ly.addLayout(vr); ly.addSpacing(12)

        # AppID + Folder
        mid = QHBoxLayout(); mid.setSpacing(20)
        ac = QVBoxLayout(); ac.setSpacing(2)
        self.lbl_appid = QLabel(t('steam_appid')); ac.addWidget(self.lbl_appid)
        self.le_appid = QLineEdit(); self.le_appid.setClearButtonEnabled(True); self.le_appid.setFixedWidth(132)
        self.le_appid.textChanged.connect(lambda: self._debounce.start(400)); ac.addWidget(self.le_appid)
        self.lbl_game = QLabel(''); self.lbl_game.setObjectName('gameLabel'); self.lbl_game.setFixedHeight(16); ac.addWidget(self.lbl_game)
        self.lbl_hint = QLabel(t('appid_hint')); self.lbl_hint.setObjectName('hintLabel'); self.lbl_hint.setFixedHeight(16); ac.addWidget(self.lbl_hint)
        mid.addLayout(ac)

        fc = QVBoxLayout(); fc.setSpacing(2)
        self.lbl_dir = QLabel(t('steam_folder')); fc.addWidget(self.lbl_dir)
        fr = QHBoxLayout(); fr.setSpacing(8)
        self.le_folder = QLineEdit(); self.le_folder.setPlaceholderText(t('placeholder_dir'))
        if self._cfg.get('last_folder'): self.le_folder.setText(self._cfg['last_folder'])
        fr.addWidget(self.le_folder)
        self.btn_dir = QPushButton(t('browse')); self.btn_dir.setStyleSheet('padding:6px 10px;'); self.btn_dir.clicked.connect(self._browse_folder)
        fr.addWidget(self.btn_dir); fc.addLayout(fr)
        for _ in range(2): sp=QLabel(''); sp.setFixedHeight(16); fc.addWidget(sp)
        mid.addLayout(fc); ly.addLayout(mid); ly.addSpacing(14)

        # progress
        self.lbl_prog = QLabel(t('progress')); ly.addWidget(self.lbl_prog); ly.addSpacing(4)
        self.pb = QProgressBar(); self.pb.setRange(0,100); self.pb.setTextVisible(False); self.pb.setFixedHeight(18); ly.addWidget(self.pb)
        ly.addSpacing(6)
        pr = QHBoxLayout(); pr.setContentsMargins(0,0,0,0)
        self.lbl_pct = QLabel('0%'); self.lbl_pct.setObjectName('pctLabel'); pr.addWidget(self.lbl_pct); pr.addStretch()
        self.lbl_status = QLabel(t('ready')); self.lbl_status.setObjectName('statusLabel'); pr.addWidget(self.lbl_status)
        ly.addLayout(pr); ly.addSpacing(14)

        # import btn
        self.btn_import = QPushButton(t('start_import')); self.btn_import.setObjectName('btnImport')
        self.btn_import.setFixedHeight(42); self.btn_import.clicked.connect(self._start_import)
        ly.addWidget(self.btn_import)

        # debounce timer
        self._debounce = QTimer(); self._debounce.setSingleShot(True); self._debounce.timeout.connect(self._lookup_appid)

    # ── lang ────────────────────────────────────────────────────────────
    def _toggle_lang(self):
        global LANG; LANG = 'en' if LANG == 'zh' else 'zh'; self._cfg['lang'] = LANG; _save_cfg(self._cfg)
        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(t('title')); self.lbl_title.setText(t('title')); self.btn_lang.setText(t('lang_btn'))
        self.lbl_vid.setText(t('video_file')); self.btn_vid.setText(t('browse')); self.le_video.setPlaceholderText(t('placeholder_vid'))
        self.lbl_appid.setText(t('steam_appid')); self.lbl_hint.setText(t('appid_hint'))
        self.lbl_dir.setText(t('steam_folder')); self.btn_dir.setText(t('browse')); self.le_folder.setPlaceholderText(t('placeholder_dir'))
        self.lbl_prog.setText(t('progress'))
        if self.btn_import.isEnabled(): self.btn_import.setText(t('start_import'))
        else: self.btn_import.setText(t('importing'))
        if self.lbl_status.text() in ('就绪','Ready'): self.lbl_status.setText(t('ready'))
        self._lookup_appid()

    # ── appid lookup ────────────────────────────────────────────────────
    def _lookup_appid(self):
        try: appid = int(self.le_appid.text().strip())
        except: self.lbl_game.setText(''); return
        if appid <= 0: self.lbl_game.setText(''); return
        # always prefer local dictionary
        if appid in GAME_NAMES:
            self._show_name(GAME_NAMES[appid])
            return
        if appid in _cache:
            self._show_name(_cache[appid])
            return
        self.lbl_game.setText(f'Game {appid}')
        self.lbl_game.setObjectName('hintLabel'); self.lbl_game.setStyleSheet(f'color:{SUB};font-size:11px;')
        if self._lu and self._lu.isRunning():
            try: self._lu.done.disconnect()
            except: pass
            self._lu.quit(); self._lu.wait(100)
        self._lu = NameLookup(appid)
        self._lu.done.connect(lambda aid, name: self._set_game_name(aid, name))
        self._lu.start()

    def _show_name(self, name):
        self.lbl_game.setText(f'\U0001f3ae {name}')
        self.lbl_game.setObjectName('gameLabel'); self.lbl_game.setStyleSheet(f'color:{ACCENT};font-size:11px;font-weight:bold;')

    def _set_game_name(self, appid, name):
        try: cur = int(self.le_appid.text().strip())
        except: return
        if cur != appid: return
        self._show_name(name)

    # ── browse ──────────────────────────────────────────────────────────
    def _browse_video(self):
        p, _ = QFileDialog.getOpenFileName(self, t('browse_video'), '', t('video_filter'))
        if p: self.le_video.setText(p)

    def _browse_folder(self):
        p = QFileDialog.getExistingDirectory(self, t('steam_folder'))
        if p: self.le_folder.setText(p)

    # ── import ──────────────────────────────────────────────────────────
    def _start_import(self):
        video = self.le_video.text().strip()
        if not video or not os.path.isfile(video): QMessageBox.critical(self, t('error'), t('err_no_video')); return
        try: appid = int(self.le_appid.text().strip() or '0')
        except: QMessageBox.critical(self, t('error'), t('err_appid')); return
        if appid <= 0: QMessageBox.critical(self, t('error'), t('err_appid')); return
        folder = self.le_folder.text().strip()
        if not folder or not os.path.isdir(folder): QMessageBox.critical(self, t('error'), t('err_no_dir')); return
        if not os.path.isfile(os.path.join(folder, 'gamerecording.pb')): QMessageBox.critical(self, t('error'), t('err_no_pb')); return
        self.btn_import.setEnabled(False); self.btn_import.setText(t('importing'))
        self.pb.setValue(0); self.lbl_pct.setText('0%'); self.lbl_status.setText(t('starting'))
        self._worker = ImportWorker(video, appid, folder)
        self._worker.progress.connect(lambda p,s: (self.pb.setValue(p), self.lbl_pct.setText(f'{p}%'), self.lbl_status.setText(s)))
        self._worker.finished.connect(self._done); self._worker.start()

    def _done(self, ok, msg):
        self.btn_import.setEnabled(True); self.btn_import.setText(t('start_import')); self._worker = None
        if ok:
            self._cfg['last_folder'] = self.le_folder.text(); _save_cfg(self._cfg)
            self.le_video.clear(); self.pb.setValue(0); self.lbl_pct.setText('0%')
            QMessageBox.information(self, t('success'), f'{t("success_msg")}\n\n{msg}')
            self.lbl_status.setText(t('ready'))
        else:
            QMessageBox.critical(self, t('failed'), msg)
            self.lbl_status.setText(t('failed')); self.pb.setValue(0); self.lbl_pct.setText('0%')

# ── main ────────────────────────────────────────────────────────────────────
def main():
    if not _check_ffmpeg():
        app = QApplication(sys.argv); QMessageBox.critical(None, t('err_ffmpeg_title'), t('err_ffmpeg')); sys.exit(1)
    app = QApplication(sys.argv); app.setStyle('Fusion'); w = MainWindow(); w.show(); sys.exit(app.exec())

if __name__ == '__main__': main()
