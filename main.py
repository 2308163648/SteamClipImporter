"""Steam Clip Importer — PyQt5 GUI entry point."""

import json
import os
import shutil
import sys
import threading

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QProgressBar, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox,
    QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

from importer import import_video

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def _config_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'SteamClipImporter.json')


def _load_config():
    path = _config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(cfg: dict):
    with open(_config_path(), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _check_ffmpeg():
    for tool in ('ffmpeg', 'ffprobe'):
        if shutil.which(tool) is None:
            return False
    return True

# ---------------------------------------------------------------------------
# worker thread
# ---------------------------------------------------------------------------

class ImportWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, video, appid, folder):
        super().__init__()
        self.video = video
        self.appid = appid
        self.folder = folder
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            clip_dir = import_video(
                self.video, self.appid, self.folder,
                progress_cb=lambda p, s: self.progress.emit(int(p), s),
            )
            self.finished.emit(True, clip_dir)
        except Exception as e:
            self.finished.emit(False, str(e))

# ---------------------------------------------------------------------------
# main window
# ---------------------------------------------------------------------------

ACCENT = '#2563eb'
ACCENT_HOVER = '#1d4ed8'
BG = '#ffffff'
FG = '#1e293b'
SUB = '#94a3b8'
INPUT_BG = '#f8fafc'
BORDER = '#e2e8f0'


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Steam Clip Importer')
        self.setMinimumSize(520, 360)
        self.resize(580, 400)

        # icon
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.ico')
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

        self._worker = None
        self._cfg = _load_config()

        self._build()
        self._centre()

    def _centre(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _build(self):
        self.setStyleSheet(f"""
            QWidget {{
                background: {BG};
                color: {FG};
                font-family: 'Microsoft YaHei UI';
                font-size: 13px;
            }}
            QLineEdit {{
                background: {INPUT_BG};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
            QPushButton {{
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 6px 14px;
                background: {BG};
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: #f1f5f9;
            }}
            QPushButton#btnImport {{
                background: {ACCENT};
                color: white;
                border: none;
                font-size: 15px;
                font-weight: bold;
                padding: 10px 0;
                border-radius: 6px;
            }}
            QPushButton#btnImport:hover {{
                background: {ACCENT_HOVER};
            }}
            QPushButton#btnImport:disabled {{
                background: #94a3b8;
            }}
            QProgressBar {{
                border: none;
                background: {BORDER};
                border-radius: 4px;
                height: 18px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {ACCENT};
                border-radius: 4px;
            }}
            QLabel#pctLabel {{
                font-size: 22px;
                font-weight: bold;
                color: {ACCENT};
            }}
            QLabel#statusLabel {{
                color: {SUB};
                font-size: 12px;
            }}
            QLabel#hintLabel {{
                color: {SUB};
                font-size: 11px;
            }}
            QLabel#titleLabel {{
                font-size: 18px;
                font-weight: bold;
                color: {FG};
            }}
            QFrame#sep {{
                background: {BORDER};
                max-height: 1px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        # title
        title = QLabel('Steam Clip Importer')
        title.setObjectName('titleLabel')
        layout.addWidget(title)
        layout.addSpacing(14)

        # video
        layout.addWidget(QLabel('视频文件'))
        vid_row = QHBoxLayout()
        vid_row.setSpacing(8)
        self.le_video = QLineEdit()
        self.le_video.setPlaceholderText('选择视频文件...')
        vid_row.addWidget(self.le_video)
        btn_vid = QPushButton('浏览')
        btn_vid.setFixedWidth(56)
        btn_vid.clicked.connect(self._browse_video)
        vid_row.addWidget(btn_vid)
        layout.addLayout(vid_row)
        layout.addSpacing(14)

        # AppID + Folder — aligned with same row structure
        mid = QHBoxLayout()
        mid.setSpacing(20)

        # AppID column: label, input, hint
        aid_col = QVBoxLayout()
        aid_col.setSpacing(2)
        aid_col.addWidget(QLabel('Steam AppID'))
        self.le_appid = QLineEdit()
        self.le_appid.setPlaceholderText('')
        self.le_appid.setClearButtonEnabled(True)
        self.le_appid.setFixedWidth(132)
        aid_col.addWidget(self.le_appid)
        hint = QLabel('举例：CS2=730, Dota2=570')
        hint.setObjectName('hintLabel')
        hint.setFixedHeight(16)
        aid_col.addWidget(hint)
        mid.addLayout(aid_col)

        # Folder column: label, input+browse, spacer (matches hint height)
        fld_col = QVBoxLayout()
        fld_col.setSpacing(2)
        fld_col.addWidget(QLabel('Steam 录像文件夹'))
        fld_row = QHBoxLayout()
        fld_row.setSpacing(8)
        self.le_folder = QLineEdit()
        last = self._cfg.get('last_folder', '')
        if last:
            self.le_folder.setText(last)
        self.le_folder.setPlaceholderText('选择包含 gamerecording.pb 的文件夹...')
        fld_row.addWidget(self.le_folder)
        btn_fld = QPushButton('浏览')
        btn_fld.setFixedWidth(56)
        btn_fld.clicked.connect(self._browse_folder)
        fld_row.addWidget(btn_fld)
        fld_col.addLayout(fld_row)
        # spacer matching hint row
        spacer = QLabel('')
        spacer.setFixedHeight(16)
        fld_col.addWidget(spacer)
        mid.addLayout(fld_col)

        layout.addLayout(mid)
        layout.addSpacing(16)

        # progress label
        layout.addWidget(QLabel('导入进度'))
        layout.addSpacing(4)

        # progress bar
        self.pb = QProgressBar()
        self.pb.setRange(0, 100)
        self.pb.setValue(0)
        self.pb.setTextVisible(False)
        self.pb.setFixedHeight(18)
        layout.addWidget(self.pb)
        layout.addSpacing(6)

        # pct + status
        pct_row = QHBoxLayout()
        pct_row.setContentsMargins(0, 0, 0, 0)
        self.lbl_pct = QLabel('0%')
        self.lbl_pct.setObjectName('pctLabel')
        pct_row.addWidget(self.lbl_pct)
        pct_row.addStretch()
        self.lbl_status = QLabel('就绪')
        self.lbl_status.setObjectName('statusLabel')
        pct_row.addWidget(self.lbl_status)
        layout.addLayout(pct_row)
        layout.addSpacing(14)

        # import button
        self.btn_import = QPushButton('开始导入')
        self.btn_import.setObjectName('btnImport')
        self.btn_import.setFixedHeight(42)
        self.btn_import.clicked.connect(self._start_import)
        layout.addWidget(self.btn_import)

    # ------------------------------------------------------------------
    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择视频文件', '',
            '视频文件 (*.mp4 *.mkv *.mov *.avi *.webm);;所有文件 (*.*)'
        )
        if path:
            self.le_video.setText(path)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, '选择 Steam 录像文件夹'
        )
        if path:
            self.le_folder.setText(path)

    # ------------------------------------------------------------------
    def _start_import(self):
        video = self.le_video.text().strip()
        if not video or not os.path.isfile(video):
            QMessageBox.critical(self, '错误', '请选择有效的视频文件')
            return

        try:
            appid = int(self.le_appid.text().strip() or '0')
            if appid <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, '错误', 'AppID 必须是一个有效的数字')
            return

        folder = self.le_folder.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.critical(self, '错误', '请选择有效的 Steam 录像文件夹')
            return

        gr_pb = os.path.join(folder, 'gamerecording.pb')
        if not os.path.isfile(gr_pb):
            QMessageBox.critical(self, '错误',
                                 f'所选文件夹中未找到 gamerecording.pb:\n{folder}')
            return

        self.btn_import.setEnabled(False)
        self.btn_import.setText('处理中...')
        self.pb.setValue(0)
        self.lbl_pct.setText('0%')
        self.lbl_status.setText('正在启动...')

        self._worker = ImportWorker(video, appid, folder)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct, status):
        self.pb.setValue(pct)
        self.lbl_pct.setText(f'{pct}%')
        self.lbl_status.setText(status)

    def _on_finished(self, success, message):
        self.btn_import.setEnabled(True)
        self.btn_import.setText('开始导入')
        self._worker = None

        if success:
            self._cfg['last_folder'] = self.le_folder.text()
            _save_config(self._cfg)
            self.le_video.clear()
            self.pb.setValue(0)
            self.lbl_pct.setText('0%')
            QMessageBox.information(self, '导入成功',
                                    f'剪辑已成功导入!\n\n{message}')
            self.lbl_status.setText('就绪')
        else:
            QMessageBox.critical(self, '导入失败', message)
            self.lbl_status.setText('导入失败')
            self.pb.setValue(0)
            self.lbl_pct.setText('0%')

# ---------------------------------------------------------------------------
def main():
    if not _check_ffmpeg():
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None, '缺少依赖',
            '未找到 ffmpeg / ffprobe。\n\n'
            '请安装 ffmpeg 并将其添加到系统 PATH 环境变量中。\n'
            '下载地址: https://ffmpeg.org/download.html'
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
