"""Steam Clip Importer — GUI entry point."""

import os
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from importer import import_video

# ---------------------------------------------------------------------------
def _check_ffmpeg():
    for tool in ('ffmpeg', 'ffprobe'):
        if shutil.which(tool) is None:
            return False
    return True

# ---------------------------------------------------------------------------
TITLE = 'Steam Clip Importer'
WIN_W = 580
WIN_H = 380

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.resizable(False, False)

        # icon — try multiple approaches for PyInstaller compatibility
        try:
            ico = os.path.join(sys._MEIPASS, 'app.ico')
        except Exception:
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.ico')
        if os.path.exists(ico):
            self.iconbitmap(ico)

        self._centre(WIN_W, WIN_H)
        self.configure(bg='#ffffff')
        self._running = False

        self.var_video = tk.StringVar()
        self.var_appid = tk.StringVar()
        self.var_folder = tk.StringVar()
        self.var_progress = tk.DoubleVar(value=0)
        self.var_status = tk.StringVar(value='就绪')

        self._build()

    def _centre(self, w, h):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')

    def _build(self):
        BG = '#ffffff'
        FG = '#1e293b'
        SUB = '#94a3b8'
        ACCENT = '#2563eb'
        MARGIN = 20

        self.configure(bg=BG)

        # ---- title ----
        tk.Label(self, text='Steam Clip Importer', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 16, 'bold')).pack(anchor='w', padx=MARGIN, pady=(MARGIN, 12))

        # ---- video file ----
        tk.Label(self, text='视频文件', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=MARGIN)

        vid_row = tk.Frame(self, bg=BG)
        vid_row.pack(fill='x', padx=MARGIN, pady=(2, 12))
        tk.Entry(vid_row, textvariable=self.var_video, font=('Microsoft YaHei UI', 9),
                 relief='solid', borderwidth=1, bg='#f8fafc').pack(side='left', fill='x', expand=True, ipady=3)
        tk.Button(vid_row, text='浏览', command=self._browse_video, width=6,
                  font=('Microsoft YaHei UI', 9), bg='#f1f5f9', relief='solid', borderwidth=1,
                  cursor='hand2').pack(side='left', padx=(8, 0), ipady=3)

        # ---- AppID + folder side by side (shared grid for alignment) ----
        mid_row = tk.Frame(self, bg=BG)
        mid_row.pack(fill='x', padx=MARGIN, pady=(0, 12))
        mid_row.columnconfigure(1, weight=1)

        # labels
        tk.Label(mid_row, text='Steam AppID', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 9)).grid(row=0, column=0, sticky='w')
        tk.Label(mid_row, text='Steam 录像文件夹', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 9)).grid(row=0, column=1, sticky='w', padx=(20, 0))

        # entry row
        tk.Entry(mid_row, textvariable=self.var_appid, width=14, font=('Microsoft YaHei UI', 9),
                 relief='solid', borderwidth=1, bg='#f8fafc').grid(row=1, column=0, sticky='w', ipady=3)

        fld_row = tk.Frame(mid_row, bg=BG)
        fld_row.grid(row=1, column=1, sticky='ew', padx=(20, 0))
        tk.Entry(fld_row, textvariable=self.var_folder, font=('Microsoft YaHei UI', 9),
                 relief='solid', borderwidth=1, bg='#f8fafc').pack(side='left', fill='x', expand=True, ipady=3)
        tk.Button(fld_row, text='浏览', command=self._browse_folder, width=6,
                  font=('Microsoft YaHei UI', 9), bg='#f1f5f9', relief='solid', borderwidth=1,
                  cursor='hand2').pack(side='left', padx=(8, 0), ipady=3)

        # hint
        tk.Label(mid_row, text='举例：CS2=730, Dota2=570', bg=BG, fg=SUB,
                 font=('Microsoft YaHei UI', 8)).grid(row=2, column=0, sticky='w')

        # ---- progress ----
        tk.Label(self, text='导入进度', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=MARGIN, pady=(6, 2))

        self.pb_canvas = tk.Canvas(self, height=22, bg='#e2e8f0', bd=0, highlightthickness=0)
        self.pb_canvas.pack(fill='x', padx=MARGIN, pady=(2, 0))
        self.pb_bar = self.pb_canvas.create_rectangle(0, 0, 0, 22, fill=ACCENT, width=0)

        def _update_bar(*_):
            pct = self.var_progress.get() / 100.0
            w = self.pb_canvas.winfo_width()
            self.pb_canvas.coords(self.pb_bar, 0, 0, w * pct, 22)

        self.var_progress.trace_add('write', _update_bar)
        self.pb_canvas.bind('<Configure>', _update_bar)

        prog_row = tk.Frame(self, bg=BG)
        prog_row.pack(fill='x', padx=MARGIN, pady=(4, 6))
        self.lbl_pct = tk.Label(prog_row, text='0%', bg=BG, fg=ACCENT,
                                font=('Microsoft YaHei UI', 14, 'bold'))
        self.lbl_pct.pack(side='left')
        tk.Label(prog_row, textvariable=self.var_status, bg=BG, fg=SUB,
                 font=('Microsoft YaHei UI', 9)).pack(side='right')

        # ---- button ----
        self.btn_import = tk.Button(self, text='开始导入', command=self._start_import,
                                    bg=ACCENT, fg='white', font=('Microsoft YaHei UI', 11, 'bold'),
                                    relief='flat', cursor='hand2', width=18, height=2,
                                    activebackground='#1d4ed8', activeforeground='white')
        self.btn_import.pack(pady=(12, MARGIN))

    # ------------------------------------------------------------------
    def _browse_video(self):
        path = filedialog.askopenfilename(
            title='选择视频文件',
            filetypes=[('视频文件', '*.mp4 *.mkv *.mov *.avi *.webm'), ('所有文件', '*.*')],
        )
        if path:
            self.var_video.set(path)

    def _browse_folder(self):
        path = filedialog.askdirectory(title='选择 Steam 录像文件夹（包含 gamerecording.pb 和 clips/）')
        if path:
            self.var_folder.set(path)

    # ------------------------------------------------------------------
    def _start_import(self):
        if self._running:
            return

        video = self.var_video.get().strip()
        if not video or not os.path.isfile(video):
            messagebox.showerror('错误', '请选择有效的视频文件')
            return

        try:
            appid = int(self.var_appid.get().strip())
        except ValueError:
            messagebox.showerror('错误', 'AppID 必须是一个数字')
            return

        folder = self.var_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror('错误', '请选择有效的 Steam 录像文件夹')
            return

        gr_pb = os.path.join(folder, 'gamerecording.pb')
        if not os.path.isfile(gr_pb):
            messagebox.showerror('错误', f'所选文件夹中未找到 gamerecording.pb:\n{folder}')
            return

        self._running = True
        self.btn_import.config(state='disabled', text='处理中...', bg='#94a3b8')
        self.var_progress.set(0)
        self.lbl_pct.config(text='0%')
        self.var_status.set('正在启动...')

        t = threading.Thread(target=self._run_import, args=(video, appid, folder), daemon=True)
        t.start()

    def _run_import(self, video, appid, folder):
        def progress(pct, status):
            self.var_progress.set(pct)
            self.lbl_pct.config(text=f'{int(pct)}%')
            self.var_status.set(status)

        try:
            clip_dir = import_video(video, appid, folder, progress_cb=progress)
            self.after(0, lambda: self._done(None, clip_dir))
        except Exception as e:
            self.after(0, lambda: self._done(str(e), None))

    def _done(self, error, clip_dir):
        self._running = False
        self.btn_import.config(state='normal', text='开始导入', bg='#2563eb')
        if error:
            messagebox.showerror('导入失败', error)
            self.var_status.set('导入失败')
            self.var_progress.set(0)
            self.lbl_pct.config(text='0%')
        else:
            messagebox.showinfo('导入成功', f'剪辑已成功导入!\n\n{clip_dir}')
            self.var_status.set('就绪')

# ---------------------------------------------------------------------------
def main():
    if not _check_ffmpeg():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            '缺少依赖',
            '未找到 ffmpeg / ffprobe。\n\n'
            '请安装 ffmpeg 并将其添加到系统 PATH 环境变量中。\n'
            '下载地址: https://ffmpeg.org/download.html'
        )
        root.destroy()
        sys.exit(1)

    app = App()
    app.mainloop()

if __name__ == '__main__':
    main()
