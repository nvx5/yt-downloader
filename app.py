"""yt-dlp GUI; FFmpeg via imageio-ffmpeg. Optional exe: see requirements.txt top lines."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time
import yt_dlp
import os
import shutil

# Display label -> yt-dlp format string (merge path needs FFmpeg)
_MP4_QUALITY_MERGE: dict[str, str] = {
    "Best": "bestvideo+bestaudio/best",
    "2160p (4K)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "240p": "bestvideo[height<=240]+bestaudio/best[height<=240]/best",
    "144p": "bestvideo[height<=144]+bestaudio/best[height<=144]/best",
    "Worst (smallest)": "worstvideo+worstaudio/worst",
}
_MP4_QUALITY_SINGLE: dict[str, str] = {
    "Best": "best[ext=mp4]/best[ext=webm]/best",
    "2160p (4K)": "best[height<=2160][ext=mp4]/best[height<=2160][ext=webm]/best[height<=2160]/best",
    "1440p": "best[height<=1440][ext=mp4]/best[height<=1440][ext=webm]/best[height<=1440]/best",
    "1080p": "best[height<=1080][ext=mp4]/best[height<=1080][ext=webm]/best[height<=1080]/best",
    "720p": "best[height<=720][ext=mp4]/best[height<=720][ext=webm]/best[height<=720]/best",
    "480p": "best[height<=480][ext=mp4]/best[height<=480][ext=webm]/best[height<=480]/best",
    "360p": "best[height<=360][ext=mp4]/best[height<=360][ext=webm]/best[height<=360]/best",
    "240p": "best[height<=240][ext=mp4]/best[height<=240][ext=webm]/best[height<=240]/best",
    "144p": "best[height<=144][ext=mp4]/best[height<=144][ext=webm]/best[height<=144]/best",
    "Worst (smallest)": "worst",
}
_MP4_QUALITY_KEYS: tuple[str, ...] = tuple(_MP4_QUALITY_MERGE.keys())

_MP3_QUALITY: dict[str, str] = {
    "Best": "bestaudio/best",
    "High (≤192 kbps)": "bestaudio[abr<=192]/bestaudio/best",
    "Medium (≤128 kbps)": "bestaudio[abr<=128]/bestaudio/best",
    "Low (≤96 kbps)": "bestaudio[abr<=96]/bestaudio/best",
    "Smallest (≤64 kbps)": "bestaudio[abr<=64]/bestaudio/best",
}
_MP3_QUALITY_KEYS: tuple[str, ...] = tuple(_MP3_QUALITY.keys())


class YoutubeDownloaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.video_data: list = []
        self.check_vars: list[tk.BooleanVar] = []

        root.title("YouTube Downloader")
        self._dl_index = 1
        self._dl_total = 1
        self._title_max = 48
        self._prog_pct = 0.0
        self._prog_line = ""
        self._download_canvas_packed = False
        # Match ttk.Entry row height (Browse / channel row / download bar)
        self._download_canvas_h = 30

        root.minsize(640, 640)
        root.geometry("720x760")

        self._setup_style()
        self._build_ui()

    def _bundled_ffmpeg_exe(self) -> str | None:
        try:
            import imageio_ffmpeg

            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.isfile(exe):
                return os.path.abspath(exe)
        except Exception:
            pass
        return None

    def _system_ffmpeg_exe(self) -> str | None:
        w = shutil.which("ffmpeg")
        return os.path.abspath(w) if w else None

    def _ffmpeg_exe(self) -> str | None:
        return self._bundled_ffmpeg_exe() or self._system_ffmpeg_exe()

    def _ffmpeg_available(self) -> bool:
        return self._ffmpeg_exe() is not None

    def _ffmpeg_location_opt(self) -> dict:
        exe = self._ffmpeg_exe()
        if not exe:
            return {}
        return {"ffmpeg_location": exe}

    def _on_format_change(self, *_args: object) -> None:
        if self.format_var.get() == "MP3":
            self.quality_combo.configure(values=_MP3_QUALITY_KEYS)
            if self.quality_var.get() not in _MP3_QUALITY:
                self.quality_var.set(_MP3_QUALITY_KEYS[0])
        else:
            self.quality_combo.configure(values=_MP4_QUALITY_KEYS)
            if self.quality_var.get() not in _MP4_QUALITY_MERGE:
                self.quality_var.set(_MP4_QUALITY_KEYS[0])

    def _selected_quality_label(self) -> str:
        label = (self.quality_var.get() or "").strip()
        if self.format_var.get() == "MP3":
            if label not in _MP3_QUALITY:
                return _MP3_QUALITY_KEYS[0]
            return label
        if label not in _MP4_QUALITY_MERGE:
            return _MP4_QUALITY_KEYS[0]
        return label

    def _mp4_ydl_opts(self, base: dict) -> dict:
        label = self._selected_quality_label()
        if self._ffmpeg_available():
            return {
                **base,
                "format": _MP4_QUALITY_MERGE[label],
                "merge_output_format": "mp4",
            }
        return {**base, "format": _MP4_QUALITY_SINGLE[label]}

    def _setup_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Softer, readable defaults
        style.configure("TFrame", background="#f4f4f5")
        style.configure("TLabelframe", background="#f4f4f5", foreground="#18181b")
        style.configure("TLabelframe.Label", background="#f4f4f5", foreground="#3f3f46", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#f4f4f5", foreground="#3f3f46", font=("Segoe UI", 9))
        style.configure("Muted.TLabel", foreground="#71717a", font=("Segoe UI", 8))
        style.configure(
            "DockHint.TLabel",
            background="#fafafa",
            foreground="#52525b",
            font=("Segoe UI", 9),
        )
        # Vertical padding aligned with TEntry row height (clam)
        _btn_pad = (10, 2)
        style.configure("TButton", font=("Segoe UI", 9), padding=_btn_pad)
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), padding=_btn_pad)
        style.configure("TRadiobutton", background="#f4f4f5", font=("Segoe UI", 9))
        style.configure("TEntry", font=("Segoe UI", 9))
        style.map("TEntry", fieldbackground=[("readonly", "#e4e4e7")])

        self.root.configure(bg="#f4f4f5")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(20, 16))
        outer.pack(fill=tk.BOTH, expand=True)

        # Bottom dock: progress first, then hint + download (stays visible).
        bottom = ttk.Frame(outer)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))

        dock = tk.Frame(bottom, bg="#e4e4e7", padx=1, pady=1)
        dock.pack(fill=tk.X)
        dock_inner = tk.Frame(dock, bg="#fafafa", padx=14, pady=12)
        dock_inner.pack(fill=tk.BOTH)

        ttk.Label(
            dock_inner,
            text="Ticked channel videos are used when at least one is selected; otherwise your URL list is used.",
            style="DockHint.TLabel",
            wraplength=640,
            justify=tk.CENTER,
            anchor=tk.CENTER,
        ).pack(fill=tk.X, pady=(0, 12))

        self._dl_zone = tk.Frame(dock_inner, bg="#fafafa")
        self._dl_zone.pack(fill=tk.X)

        self.btn_download = tk.Button(
            self._dl_zone,
            text="Download",
            command=self.download_unified,
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief=tk.FLAT,
            padx=14,
            pady=4,
            cursor="hand2",
        )
        self.btn_download.pack(fill=tk.X)

        self.download_canvas = tk.Canvas(
            self._dl_zone,
            height=self._download_canvas_h,
            highlightthickness=0,
            bg="#fafafa",
        )
        self.download_canvas.bind("<Configure>", self._on_download_canvas_configure)

        main = ttk.Frame(outer)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Shared: folder + format (always at top)
        lf_common = ttk.LabelFrame(main, text="Save location & format", padding=(12, 10))
        lf_common.pack(fill=tk.X, pady=(0, 12))

        path_row = ttk.Frame(lf_common)
        path_row.pack(fill=tk.X)
        ttk.Label(path_row, text="Folder").pack(side=tk.LEFT, padx=(0, 8))
        self.entry_path = ttk.Entry(path_row)
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(path_row, text="Browse…", command=self.browse_folder, width=10).pack(side=tk.RIGHT)

        fmt_row = ttk.Frame(lf_common)
        fmt_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(fmt_row, text="Output format").pack(side=tk.LEFT, padx=(0, 12))
        self.format_var = tk.StringVar(value="MP4")
        for val, label in (("MP4", "MP4 (video)"), ("MP3", "MP3 (audio only)")):
            ttk.Radiobutton(fmt_row, text=label, variable=self.format_var, value=val).pack(side=tk.LEFT, padx=(0, 16))

        quality_row = ttk.Frame(lf_common)
        quality_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(quality_row, text="Quality").pack(side=tk.LEFT, padx=(0, 12))
        self.quality_var = tk.StringVar(value=_MP4_QUALITY_KEYS[0])
        self.quality_combo = ttk.Combobox(
            quality_row,
            textvariable=self.quality_var,
            values=_MP4_QUALITY_KEYS,
            state="readonly",
            width=28,
            font=("Segoe UI", 9),
        )
        self.quality_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.format_var.trace_add("write", self._on_format_change)
        ttk.Label(
            lf_common,
            text="Presets are upper limits: you get the best stream the site offers, up to that cap (e.g. a 1080p-only video still downloads in 1080p if you pick 1440p).",
            style="Muted.TLabel",
            wraplength=620,
        ).pack(anchor=tk.W, pady=(4, 0))

        # Direct download
        lf_direct = ttk.LabelFrame(main, text="Direct download", padding=(12, 10))
        lf_direct.pack(fill=tk.BOTH, expand=False, pady=(0, 12))
        ttk.Label(
            lf_direct,
            text="One URL per line — supports single videos, playlists, or multiple links.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))
        self.text_urls = tk.Text(
            lf_direct,
            height=5,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#d4d4d8",
            highlightcolor="#3b82f6",
            padx=8,
            pady=8,
        )
        self.text_urls.pack(fill=tk.BOTH, expand=True)

        # Channel / playlist
        lf_channel = ttk.LabelFrame(main, text="Channel or playlist", padding=(12, 10))
        lf_channel.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        ttk.Label(
            lf_channel,
            text="Paste a channel or playlist URL, then fetch the list and tick videos to download.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        fetch_row = ttk.Frame(lf_channel)
        fetch_row.pack(fill=tk.X)
        self.entry_channel = ttk.Entry(fetch_row)
        self.entry_channel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(fetch_row, text="Fetch list", command=self.fetch_videos, style="Accent.TButton").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(fetch_row, text="Select all", command=self.select_all_videos).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(fetch_row, text="Clear selection", command=self.clear_video_selection).pack(side=tk.LEFT)

        # Scrollable video list
        list_border = tk.Frame(lf_channel, bg="#e4e4e7", padx=1, pady=1)
        list_border.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.canvas = tk.Canvas(
            list_border,
            highlightthickness=0,
            bg="white",
            height=260,
        )
        vsb = ttk.Scrollbar(list_border, orient=tk.VERTICAL, command=self.canvas.yview)
        self.frame_videos = tk.Frame(self.canvas, bg="white")

        self.frame_videos.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self._video_window = self.canvas.create_window((0, 0), window=self.frame_videos, anchor=tk.NW)

        def _on_canvas_configure(event: tk.Event) -> None:
            self.canvas.itemconfigure(self._video_window, width=event.width)

        self.canvas.bind("<Configure>", _on_canvas_configure)
        self.canvas.configure(yscrollcommand=vsb.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _bind_mousewheel(self, _event: tk.Event | None = None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event | None = None) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _fit_status_line(self, s: str, max_chars: int = 78) -> str:
        s = s.strip() or "…"
        if len(s) <= max_chars:
            return s
        return s[: max_chars - 1] + "…"

    def _on_download_canvas_configure(self, event: tk.Event) -> None:
        if not self._download_canvas_packed:
            return
        self._redraw_download_canvas(event.width, event.height)

    def _redraw_download_canvas(self, w: int | None = None, h: int | None = None) -> None:
        cav = self.download_canvas
        if w is None or h is None:
            cav.update_idletasks()
            w = max(cav.winfo_width(), 4)
            h = max(cav.winfo_height(), self._download_canvas_h)
        if w < 4:
            return
        cav.delete("all")
        trough = "#94a3b8"
        fill_c = "#2563eb"
        cav.create_rectangle(0, 0, w, h, fill=trough, outline="")
        pw = int(w * max(0.0, min(100.0, self._prog_pct)) / 100.0)
        if pw > 0:
            cav.create_rectangle(0, 0, pw, h, fill=fill_c, outline="")
        line = self._fit_status_line(self._prog_line)
        cav.create_text(
            w // 2,
            h // 2,
            text=line,
            fill="white",
            font=("Segoe UI", 9, "bold"),
        )

    def _begin_download_ui(self) -> None:
        self.btn_download.config(state=tk.DISABLED)
        self._prog_pct = 0.0
        self._prog_line = "Starting…"
        self.btn_download.pack_forget()
        self.download_canvas.pack(fill=tk.X)
        self._download_canvas_packed = True
        self.download_canvas.update_idletasks()
        self._redraw_download_canvas()

    def _end_download_ui(self) -> None:
        self._download_canvas_packed = False
        self.download_canvas.pack_forget()
        self.btn_download.pack(fill=tk.X)
        self.btn_download.config(state=tk.NORMAL)
        self._prog_pct = 0.0
        self._prog_line = ""

    def _truncate_title(self, title: str) -> str:
        title = (title or "").strip() or "…"
        m = self._title_max
        if len(title) <= m:
            return title
        return title[: m - 1] + "…"

    def _progress_pct_float(self, d: dict) -> tuple[str, float | None]:
        """Bracket text and bar value 0–100; bar None if unknown."""
        raw = (d.get("_percent_str") or "").strip().rstrip("%")
        if raw:
            try:
                v = float(raw)
                bracket = f"{v:.1f}%"
                return bracket, max(0.0, min(100.0, v))
            except ValueError:
                pass
        db = d.get("downloaded_bytes")
        tb = d.get("total_bytes") or d.get("total_bytes_estimate")
        if isinstance(db, int) and isinstance(tb, int) and tb > 0:
            v = 100.0 * db / tb
            return f"{v:.1f}%", max(0.0, min(100.0, v))
        return "…", None

    def _enqueue_progress_ui(
        self,
        title: str,
        pct_bracket: str,
        bar_value: float | None,
    ) -> None:
        def apply() -> None:
            if not self._download_canvas_packed:
                return
            cap = self._truncate_title(title)
            self._prog_line = f"{cap} ({pct_bracket}) [{self._dl_index}/{self._dl_total}]"
            if bar_value is not None:
                self._prog_pct = float(bar_value)
            self._redraw_download_canvas()

        self.root.after(0, apply)

    def _make_progress_hook(self):
        last_t = [0.0]

        def hook(d: dict) -> None:
            status = d.get("status")
            info = d.get("info_dict") or {}
            title = str(info.get("title") or "")

            if status == "downloading":
                now = time.monotonic()
                if now - last_t[0] < 0.18:
                    return
                last_t[0] = now
                bracket, bar_v = self._progress_pct_float(d)
                self._enqueue_progress_ui(title, bracket, bar_v)
            elif status == "finished":
                if not title.strip():
                    fn = d.get("filename") or ""
                    title = os.path.basename(fn) if fn else "…"
                self._enqueue_progress_ui(title, "100%", 100.0)
            elif status == "postprocessing":
                if not title.strip():
                    fn = d.get("filename") or ""
                    title = os.path.basename(fn) if fn else "…"
                self._enqueue_progress_ui(title, "100%", 100.0)
            elif status == "error":
                err = d.get("error", "unknown")
                self._enqueue_progress_ui(title, f"error: {err}", None)

        return hook

    def _build_ydl_opts(self, save_path: str, archive_file: str) -> dict:
        format_type = self.format_var.get()
        base: dict = {
            "quiet": True,
            "noprogress": False,
            "progress_hooks": [self._make_progress_hook()],
            "outtmpl": f"{save_path}/%(title)s.%(ext)s",
            "restrictfilenames": True,
            "download_archive": archive_file,
            **self._ffmpeg_location_opt(),
        }
        if format_type == "MP3":
            q = self._selected_quality_label()
            return {
                **base,
                "format": _MP3_QUALITY[q],
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            }
        return self._mp4_ydl_opts(base)

    def _run_downloads_background(self, urls: list[str]) -> None:
        save_path = self.entry_path.get().strip()
        archive_file = os.path.join(save_path, "archive.txt")
        opts = self._build_ydl_opts(save_path, archive_file)
        total = len(urls)

        def worker() -> None:
            try:
                for i, url in enumerate(urls, start=1):
                    self._dl_index = i
                    self._dl_total = total
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([url])
                self.root.after(0, lambda: self._on_download_job_done(None))
            except Exception as e:
                self.root.after(0, lambda err=e: self._on_download_job_done(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_job_done(self, err: BaseException | None) -> None:
        self._end_download_ui()
        if err is not None:
            messagebox.showerror("Download error", str(err))
        else:
            messagebox.showinfo("Done", "Download finished.")

    def browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose download folder")
        if folder:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder)

    def select_all_videos(self) -> None:
        for v in self.check_vars:
            v.set(True)

    def clear_video_selection(self) -> None:
        for v in self.check_vars:
            v.set(False)

    def _has_channel_selection(self) -> bool:
        return bool(self.check_vars) and any(v.get() for v in self.check_vars)

    def download_unified(self) -> None:
        save_path = self.entry_path.get().strip()
        if not save_path:
            messagebox.showerror("Missing folder", "Choose a download folder above.")
            return

        if self.format_var.get() == "MP3" and not self._ffmpeg_available():
            messagebox.showerror(
                "FFmpeg not available",
                "MP3 conversion needs FFmpeg, but none was found (bundled copy failed to load "
                "and none is on your PATH).\n\n"
                "Reinstall dependencies: pip install -r requirements.txt\n"
                "Or install FFmpeg and add it to PATH, then restart the app.",
            )
            return

        if self._has_channel_selection():
            selected_urls = [
                self.video_data[i]["url"]
                for i, var in enumerate(self.check_vars)
                if var.get()
            ]
            if not selected_urls:
                messagebox.showerror("Nothing selected", "Tick at least one video from the list.")
                return
            self._begin_download_ui()
            self._run_downloads_background(selected_urls)
            return

        urls = self.text_urls.get("1.0", tk.END).strip().split("\n")
        if not urls or urls == [""]:
            messagebox.showerror(
                "Nothing to download",
                "Enter at least one URL in the direct list, or fetch a channel and tick videos.",
            )
            return

        stripped = [u.strip() for u in urls if u.strip()]
        self._begin_download_ui()
        self._run_downloads_background(stripped)

    def fetch_videos(self) -> None:
        url = self.entry_channel.get().strip()

        if not url:
            messagebox.showerror("Missing URL", "Enter a channel or playlist URL.")
            return

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            self.video_data = info.get("entries", []) or []

            for widget in self.frame_videos.winfo_children():
                widget.destroy()

            self.check_vars = []

            for video in self.video_data:
                var = tk.BooleanVar(value=False)
                row = tk.Frame(self.frame_videos, bg="white")
                row.pack(fill=tk.X, padx=4, pady=2)
                cb = tk.Checkbutton(
                    row,
                    text=video.get("title", "No title"),
                    variable=var,
                    wraplength=520,
                    anchor=tk.W,
                    justify=tk.LEFT,
                    bg="white",
                    fg="#18181b",
                    activebackground="white",
                    selectcolor="white",
                    font=("Segoe UI", 9),
                    relief=tk.FLAT,
                    highlightthickness=0,
                )
                cb.pack(anchor=tk.W, fill=tk.X)
                self.check_vars.append(var)

            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

            n = len(self.video_data)
            messagebox.showinfo(
                "List loaded",
                f"{n} video(s) found. Tick the ones you want, then press Download at the bottom.",
            )

        except Exception as e:
            messagebox.showerror("Could not fetch", str(e))


def main() -> None:
    root = tk.Tk()
    YoutubeDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
