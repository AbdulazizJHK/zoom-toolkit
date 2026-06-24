import os
import sys
import json
import shutil
import random
import threading
import datetime
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

try:
    from mutagen import File
except ImportError:
    pass

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False

# Drag-and-drop is optional; the app degrades to Browse-only if unavailable.
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False


def hijri_gregorian_cls():
    """Return the Gregorian->Hijri converter class, preferring the maintained
    `hijridate` package and falling back to the deprecated `hijri-converter`."""
    try:
        from hijridate import Gregorian
        return Gregorian
    except ImportError:
        from hijri_converter import Gregorian
        return Gregorian


try:
    hijri_gregorian_cls()
    HAS_HIJRI = True
except Exception:
    HAS_HIJRI = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_VERSION = "2.0"
ALL_AUDIO_EXTS = ['.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg', '.aiff', '.wma']
DEFAULT_AUDIO_EXTS = ['.wav', '.mp3']


def settings_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "ZoomToolkit")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        pass
    return os.path.join(folder, "config.json")


def load_settings():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def open_in_explorer(path):
    """Open a folder in the OS file manager (best effort, cross-platform)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: type-checker — Windows only
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False

# ── "Field Console" palette ──────────────────────────────────────────────
# Cool graphite metal with one warm amber signal colour, echoing the black
# Zoom field recorders these recordings come off of.
THEME = {
    "bg":        "#0E1217",   # app base — cool graphite
    "panel":     "#161D26",   # raised tool panel
    "panel_2":   "#1B232E",   # nested surface (log body, dropdowns)
    "well":      "#0E141B",   # sunken input wells
    "well_bd":   "#313C49",   # input border (reads against the well)
    "line":      "#27313D",   # hairline seams
    "line_soft": "#202935",
    "amber":     "#E6A23C",   # primary signal
    "amber_hi":  "#F4B85C",   # hover / peak
    "amber_deep":"#9C6A1C",   # selected tab (keeps light text legible)
    "amber_dim": "#5C4A2A",   # meter at rest
    "text":      "#E8EDF4",   # primary text
    "muted":     "#828E9D",   # secondary text
    "faint":     "#5A6573",   # captions
    "green":     "#52B07C",   # auto-sort action
    "green_hi":  "#67C691",
    "red":       "#D2645B",   # destructive (cleaner)
    "red_hi":    "#E27A72",
    "ink":       "#0E1217",   # text on amber buttons
}

AUDIO_EXTS = ('.wav', '.mp3')


class LevelMeter(tk.Canvas):
    """A segmented audio-style level meter — the app's signature element.
    At rest it shows a dim amber baseline; while a job runs it animates like
    live recording levels, doubling as the progress indicator."""
    BARS = 18

    def __init__(self, master, width=200, height=30):
        super().__init__(master, width=width, height=height,
                         bg=THEME["panel"], highlightthickness=0, bd=0)
        self._levels = [0.16] * self.BARS
        self._targets = [0.16] * self.BARS
        self._running = False
        self._job = None
        self.bind("<Configure>", lambda e: self._draw())
        self.after(40, self._draw)

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        n = self.BARS
        gap = 3.0
        bw = (w - gap * (n - 1)) / n
        for i in range(n):
            lvl = self._levels[i]
            bh = max(2.0, lvl * (h - 3))
            x0 = i * (bw + gap)
            y1 = h - 1
            y0 = y1 - bh
            if lvl > 0.74:
                color = THEME["amber_hi"]
            elif lvl > 0.36:
                color = THEME["amber"]
            else:
                color = THEME["amber_dim"]
            self.create_rectangle(x0, y0, x0 + bw, y1, fill=color, width=0)

    def _tick(self):
        if not self._running:
            return
        for i in range(self.BARS):
            if abs(self._levels[i] - self._targets[i]) < 0.05:
                self._targets[i] = random.uniform(0.14, 1.0)
            self._levels[i] += (self._targets[i] - self._levels[i]) * 0.35
        self._draw()
        self._job = self.after(70, self._tick)

    def start(self):
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self):
        self._running = False
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self._levels = [0.16] * self.BARS
        self._targets = [0.16] * self.BARS
        self._draw()


def unique_destination(folder, filename):
    """Return a path inside `folder` for `filename` that does not collide with
    an existing file, appending _1, _2, ... to the stem as needed."""
    dest_path = Path(folder) / filename
    stem, suffix = dest_path.stem, dest_path.suffix
    counter = 1
    while dest_path.exists():
        dest_path = Path(folder) / f"{stem}_{counter}{suffix}"
        counter += 1
    return dest_path

TRANSLATIONS = {
    "English": {
        "title": "Zoom Toolkit",
        "subtitle": "FIELD AUDIO CONSOLE",
        "console": "CONSOLE",
        "status_ready": "READY",
        "status_working": "WORKING",
        "btn_settings": "Settings",
        "btn_open_folder": "Open Folder",
        "btn_save_log": "Save Log",
        "btn_stop": "Stop",
        "chk_preview": "Preview only (don't move files)",
        "log_cancelling": "Stopping after the current file…",
        "done_stopped": "Stopped",
        "done_stopped_msg": "Operation stopped by user. {} file(s) were processed.",
        "log_preview": "[PREVIEW] {} --> {}",
        "done_preview": "Preview Complete",
        "done_preview_msg": "{} file(s) would be moved. Nothing was changed.",
        "log_saved": "Log saved to: {}",
        "log_save_err": "Could not save log: {}",
        "no_output_yet": "Run a tool first — there's no output folder to open yet.",
        "no_log_dir": "No folder selected to save the log into.",
        "set_title": "Settings",
        "set_formats": "Audio file types to process",
        "set_recursive": "Include sub-folders (Cleaner & Auto-Sorter)",
        "set_date_source": "Sort by date taken from",
        "opt_date_modified": "File modified time",
        "opt_date_created": "File created time",
        "opt_date_metadata": "Recording metadata (fallback: modified)",
        "set_about": "About",
        "set_about_body": "Zoom Toolkit v{}\nField audio console for Zoom recordings.",
        "set_libs": "Hijri dates: {}   ·   Drag & drop: {}   ·   Audio info: {}",
        "set_on": "available",
        "set_off": "not installed",
        "set_save": "Save & Close",
        "confirm_sort_plan": "{} audio file(s) will be organized into {} date folder(s):\n\n{}\n\nProceed?",
        "tab_extractor": "Audio Extractor",
        "tab_cleaner": "Audio Cleaner",
        "tab_sorter": "Auto-Sorter",
        "desc_extractor": "Extracts audio files from sub-folders (e.g. SD cards) into a single directory, renaming them to prevent overwriting.",
        "desc_cleaner": "Scans a target folder and moves exceptionally short audio files (like misclicks) into a 'short_audio' folder.",
        "desc_sorter": "Automatically organizes a folder of messy audio files into clean sub-directories based on their recording date.",
        "lbl_source": "Source Folder:",
        "lbl_dest": "Destination:",
        "lbl_target": "Target Folder:",
        "lbl_thresh": "Threshold (sec):",
        "lbl_cal_format": "Calendar & Format:",
        "btn_browse": "Browse",
        "chk_auto_sort": "Auto-Sort files by Date after extraction",
        "btn_extract": "Start Extraction",
        "btn_clean": "Clean Short Audio",
        "btn_sort": "Organize Files",
        "msg_welcome": "Welcome to Zoom Toolkit!\nSelect a tool from the tabs above.\n",
        "err_missing": "Missing Information",
        "err_missing_ex": "Please select both a source folder and a destination folder.",
        "err_missing_cl": "Please select a target folder to clean.",
        "err_missing_so": "Please select a source folder to organize.",
        "err_invalid_thresh": "Please enter a valid positive integer for the threshold (seconds).",
        "err_dest_in_source": "The destination folder cannot be inside the source folder. Please choose a separate destination.",
        "warn_title": "Warning",
        "warn_clean": "Are you sure you want to move audio files shorter than {} seconds to a 'short_audio' folder in:\n\n{}?",
        "warn_sort": "Are you sure you want to MOVE audio files in:\n\n{}\n\nInto date-based subfolders?",
        "log_cancelled": "Operation cancelled by user.",
        "log_starting_ex": "Starting extraction process...\nSource: {}\nTarget: {}\n" + "-"*40,
        "log_starting_cl": "Starting cleaner process...\nTarget: {}\nThreshold: < {} seconds\n" + "-"*40,
        "log_starting_so": "Starting auto-sorter process...\nSource: {}\nCalendar: {}\nFormat: {}\n" + "-"*40,
        "log_scanning": "Scanning {} for audio files...",
        "log_copying": "Copying: {} --> {}",
        "log_err_copy": "Error copying {}: {}",
        "log_auto_sorting": "\n" + "-"*20 + "\nAuto-Sorting extracted files...",
        "log_sorted": "[SORTED] {} --> {}/",
        "log_moved": "[MOVED] {} | Length: {:.2f}s",
        "err_dep_req": "Dependency Required",
        "err_dep_hijri": "To use Hijri dates, please install 'hijri-converter'.",
        "err_dep_mutagen": "The 'mutagen' library is missing. Cannot process audio file lengths.",
        "done_ex": "Extraction Complete",
        "done_ex_msg": "Successfully copied {} files.",
        "done_cl": "Cleanup Complete",
        "done_cl_msg": "Moved {} files to the 'short_audio' folder.",
        "done_so": "Sorting Complete",
        "done_so_msg": "Moved {} audio files into date folders.",
        "error": "Error",
        "opt_gregorian": "Gregorian",
        "opt_hijri": "Hijri",
        "opt_fmt_ym": "Year-Month (YYYY-MM)",
        "opt_fmt_exact": "Exact Date (YYYY-MM-DD)",
        "err_hijri_missing": "Hijri-Converter-Missing"
    },
    "العربية": {
        "title": "أدوات زووم",
        "subtitle": "وحدة الصوت الميدانية",
        "console": "السجل",
        "status_ready": "جاهز",
        "status_working": "جارٍ العمل",
        "btn_settings": "الإعدادات",
        "btn_open_folder": "فتح المجلد",
        "btn_save_log": "حفظ السجل",
        "btn_stop": "إيقاف",
        "chk_preview": "معاينة فقط (دون نقل الملفات)",
        "log_cancelling": "جارٍ الإيقاف بعد الملف الحالي…",
        "done_stopped": "تم الإيقاف",
        "done_stopped_msg": "أوقف المستخدم العملية. تمت معالجة {} ملف.",
        "log_preview": "[معاينة] {} ← {}",
        "done_preview": "اكتملت المعاينة",
        "done_preview_msg": "سيتم نقل {} ملف. لم يتم تغيير أي شيء.",
        "log_saved": "تم حفظ السجل في: {}",
        "log_save_err": "تعذّر حفظ السجل: {}",
        "no_output_yet": "شغّل أداة أولاً — لا يوجد مجلد إخراج لفتحه بعد.",
        "no_log_dir": "لم يتم تحديد مجلد لحفظ السجل فيه.",
        "set_title": "الإعدادات",
        "set_formats": "أنواع الملفات الصوتية المراد معالجتها",
        "set_recursive": "تضمين المجلدات الفرعية (التنظيف والفرز)",
        "set_date_source": "الفرز حسب التاريخ المأخوذ من",
        "opt_date_modified": "وقت تعديل الملف",
        "opt_date_created": "وقت إنشاء الملف",
        "opt_date_metadata": "بيانات التسجيل (البديل: وقت التعديل)",
        "set_about": "حول",
        "set_about_body": "أدوات زووم v{}\nوحدة الصوت الميدانية لتسجيلات زووم.",
        "set_libs": "التواريخ الهجرية: {}   ·   السحب والإفلات: {}   ·   معلومات الصوت: {}",
        "set_on": "متاحة",
        "set_off": "غير مثبّتة",
        "set_save": "حفظ وإغلاق",
        "confirm_sort_plan": "سيتم تنظيم {} ملف صوتي في {} مجلد تاريخ:\n\n{}\n\nهل تريد المتابعة؟",
        "tab_extractor": "استخراج الصوت",
        "tab_cleaner": "تنظيف الصوت",
        "tab_sorter": "الفرز التلقائي",
        "desc_extractor": "يستخرج الملفات الصوتية من المجلدات الفرعية (مثل بطاقات SD) إلى مجلد واحد، مع إعادة تسميتها لمنع الكتابة فوقها.",
        "desc_cleaner": "يفحص المجلد المستهدف وينقل الملفات الصوتية القصيرة جداً (مثل النقرات الخاطئة) إلى مجلد 'short_audio'.",
        "desc_sorter": "ينظم تلقائيًا مجلدًا يحتوي على ملفات صوتية غير مرتبة إلى مجلدات فرعية نظيفة بناءً على تاريخ التسجيل.",
        "lbl_source": "مصدر المجلد:",
        "lbl_dest": "وجهة المجلد:",
        "lbl_target": "المجلد المستهدف:",
        "lbl_thresh": "الحد (ثواني):",
        "lbl_cal_format": "التقويم والصيغة:",
        "btn_browse": "استعراض",
        "chk_auto_sort": "الفرز التلقائي للملفات حسب التاريخ بعد الاستخراج",
        "btn_extract": "بدء الاستخراج",
        "btn_clean": "تنظيف الصوتيات القصيرة",
        "btn_sort": "تنظيم الملفات",
        "msg_welcome": "مرحباً بك في أدوات زووم!\nحدد أداة من علامات التبويب أعلاه.\n",
        "err_missing": "معلومات مفقودة",
        "err_missing_ex": "يرجى تحديد كل من المجلد المصدر والمجلد الوجهة.",
        "err_missing_cl": "يرجى تحديد مجلد مستهدف لتنظيفه.",
        "err_missing_so": "يرجى تحديد مجلد مصدر لتنظيمه.",
        "err_invalid_thresh": "يرجى إدخال عدد صحيح موجب صالح للحد الزمني (بالثواني).",
        "err_dest_in_source": "لا يمكن أن يكون المجلد الوجهة داخل المجلد المصدر. يرجى اختيار وجهة منفصلة.",
        "warn_title": "تحذير",
        "warn_clean": "هل أنت متأكد أنك تريد نقل الملفات الصوتية الأقصر من {} ثانية إلى مجلد 'short_audio' في:\n\n{}؟",
        "warn_sort": "هل أنت متأكد أنك تريد نقل الملفات الصوتية في:\n\n{}\n\nإلى مجلدات فرعية تعتمد على التاريخ؟",
        "log_cancelled": "أُلغيت العملية من قبل المستخدم.",
        "log_starting_ex": "جارٍ بدء عملية الاستخراج...\nالمصدر: {}\nالوجهة: {}\n" + "-"*40,
        "log_starting_cl": "جارٍ بدء عملية التنظيف...\nالمستهدف: {}\nالحد: < {} ثواني\n" + "-"*40,
        "log_starting_so": "جارٍ بدء عملية الفرز التلقائي...\nالمصدر: {}\nالتقويم: {}\nالصيغة: {}\n" + "-"*40,
        "log_scanning": "جارٍ فحص {} بحثًا عن ملفات صوتية...",
        "log_copying": "جارٍ النسخ: {} --> {}",
        "log_err_copy": "خطأ أثناء نسخ {}: {}",
        "log_auto_sorting": "\n" + "-"*20 + "\nجارٍ الفرز التلقائي للملفات المستخرجة...",
        "log_sorted": "[تـم الـفـرز] {} --> {}/",
        "log_moved": "[تـم الـنـقـل] {} | المدة: {:.2f}ث",
        "err_dep_req": "تتطلب اعتمادية",
        "err_dep_hijri": "لاستخدام التواريخ الهجرية، يرجى تثبيت 'hijri-converter'.",
        "err_dep_mutagen": "مكتبة 'mutagen' مفقودة. لا يمكن معالجة أطوال الملفات الصوتية.",
        "done_ex": "اكتمل الاستخراج",
        "done_ex_msg": "تم نسخ {} ملفات بنجاح.",
        "done_cl": "اكتمل التنظيف",
        "done_cl_msg": "تم نقل {} ملفات إلى مجلد 'short_audio'.",
        "done_so": "اكتمل الفرز",
        "done_so_msg": "تم نقل {} ملفات صوتية إلى مجلدات التاريخ.",
        "error": "خطأ",
        "opt_gregorian": "ميلادي (Gregorian)",
        "opt_hijri": "هجري (Hijri)",
        "opt_fmt_ym": "سنة-شهر (YYYY-MM)",
        "opt_fmt_exact": "تاريخ دقيق (YYYY-MM-DD)",
        "err_hijri_missing": "مكتبة-التحويل-الهجري-مفقودة"
    }
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ZoomToolkitApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        if HAS_DND:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception:
                pass

        self.settings = load_settings()
        self.lang_var = ctk.StringVar(value=self.settings.get("language", "English"))

        self.title(self.t("title", reshape=False))
        self.geometry("880x860")
        self.minsize(720, 760)
        self.configure(fg_color=THEME["bg"])

        try:
            self.iconbitmap(resource_path("app_icon.ico"))
        except Exception:
            pass

        # job control / preferences
        self.cancel_event = threading.Event()
        self.last_output_dir = None
        self.audio_exts = [e for e in self.settings.get("audio_exts", DEFAULT_AUDIO_EXTS) if e in ALL_AUDIO_EXTS] or list(DEFAULT_AUDIO_EXTS)
        self.recursive_var = tk.BooleanVar(value=self.settings.get("recursive", False))
        self.date_source_var = ctk.StringVar(value=self.settings.get("date_source", "modified"))

        self.ex_source_path = tk.StringVar(value=self.settings.get("ex_source", ""))
        self.ex_dest_path = tk.StringVar(value=self.settings.get("ex_dest", ""))
        self.ex_auto_sort_var = tk.BooleanVar(value=self.settings.get("ex_auto_sort", False))
        self.ex_format_vars = ctk.StringVar(value=self._fmt_value(self.settings.get("ex_format", "ym")))
        self.ex_calendar_vars = ctk.StringVar(value=self._cal_value(self.settings.get("ex_calendar", "gregorian")))

        self.cl_target_path = tk.StringVar(value=self.settings.get("cl_target", ""))
        self.cl_threshold = tk.StringVar(value=self.settings.get("cl_threshold", "30"))
        self.cl_preview_var = tk.BooleanVar(value=False)

        self.so_source_path = tk.StringVar(value=self.settings.get("so_source", ""))
        self.so_format_vars = ctk.StringVar(value=self._fmt_value(self.settings.get("so_format", "ym")))
        self.so_calendar_vars = ctk.StringVar(value=self._cal_value(self.settings.get("so_calendar", "gregorian")))
        self.so_preview_var = tk.BooleanVar(value=False)

        self.main_container = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()

    # ── settings persistence ─────────────────────────────────────────────
    def _cal_value(self, token):
        return self.t("opt_hijri" if token == "hijri" else "opt_gregorian", reshape=False)

    def _fmt_value(self, token):
        return self.t("opt_fmt_exact" if token == "exact" else "opt_fmt_ym", reshape=False)

    def _collect_settings(self):
        return {
            "language": self.lang_var.get(),
            "ex_source": self.ex_source_path.get(),
            "ex_dest": self.ex_dest_path.get(),
            "ex_auto_sort": bool(self.ex_auto_sort_var.get()),
            "ex_calendar": "hijri" if self._is_hijri(self.ex_calendar_vars.get()) else "gregorian",
            "ex_format": "exact" if "DD" in self.ex_format_vars.get() else "ym",
            "cl_target": self.cl_target_path.get(),
            "cl_threshold": self.cl_threshold.get(),
            "so_source": self.so_source_path.get(),
            "so_calendar": "hijri" if self._is_hijri(self.so_calendar_vars.get()) else "gregorian",
            "so_format": "exact" if "DD" in self.so_format_vars.get() else "ym",
            "audio_exts": self.audio_exts,
            "recursive": bool(self.recursive_var.get()),
            "date_source": self.date_source_var.get(),
        }

    def _save_settings(self):
        try:
            with open(settings_path(), "w", encoding="utf-8") as f:
                json.dump(self._collect_settings(), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _on_close(self):
        self._save_settings()
        self.destroy()

    def _set_window_icon(self, win, name):
        try:
            win.iconbitmap(resource_path(name))
        except Exception:
            pass

    # ── drag & drop ──────────────────────────────────────────────────────
    def _enable_dnd(self, widget, var):
        if not HAS_DND:
            return
        target = getattr(widget, "_entry", widget)  # register on the inner tk.Entry
        try:
            target.drop_target_register(DND_FILES)
            target.dnd_bind('<<Drop>>', lambda e, v=var: self._on_drop(e, v))
        except Exception:
            pass

    def _on_drop(self, event, var):
        data = (event.data or "").strip()
        if data.startswith('{') and '}' in data:
            path = data[1:data.index('}')]            # tkdnd braces paths with spaces
        else:
            path = data.split()[0] if data else ""
        path = path.strip()
        if os.path.isdir(path):
            var.set(path)
        elif os.path.isfile(path):
            var.set(os.path.dirname(path))

    # ── file enumeration & dates ─────────────────────────────────────────
    def _iter_audio(self, directory, recursive):
        directory = Path(directory)
        try:
            items = directory.rglob('*') if recursive else directory.iterdir()
            return sorted(p for p in items if p.is_file() and p.suffix.lower() in self.audio_exts)
        except Exception:
            return []

    def _file_dt(self, filepath):
        src = self.date_source_var.get()
        if src == "created":
            try:
                return datetime.datetime.fromtimestamp(os.path.getctime(filepath))
            except Exception:
                pass
        elif src == "metadata":
            dt = self._metadata_date(filepath)
            if dt:
                return dt
        return datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

    def _metadata_date(self, filepath):
        if 'File' not in globals():
            return None
        try:
            audio = File(str(filepath))
            tags = getattr(audio, "tags", None) or {}
            raw = None
            for key in ("TDRC", "TDOR", "originaldate", "date", "©day", "year", "creation_time"):
                try:
                    val = tags.get(key)
                except Exception:
                    val = None
                if val:
                    raw = val[0] if isinstance(val, list) else val
                    break
            if raw is None:
                return None
            s = str(raw).strip()
            for fmt, n in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
                try:
                    return datetime.datetime.strptime(s[:n], fmt)
                except Exception:
                    continue
        except Exception:
            return None
        return None

    # ── job control / progress ───────────────────────────────────────────
    def _request_cancel(self):
        self.cancel_event.set()
        self.log_message(self.t("log_cancelling"))
        try:
            self.btn_stop.configure(state="disabled")
        except Exception:
            pass

    def _begin_job(self):
        self.cancel_event.clear()
        self.set_ui_state("disabled")
        self.meter.start()
        self._set_status(True)
        self.progress.set(0)
        self.progress.grid()
        self.progress_label.configure(text="")
        self.btn_stop.configure(state="normal")
        self.btn_stop.pack(side=self._ctrl_side, padx=8, before=self.progress_label)
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", "end")
        self.log_box.configure(state="disabled")

    def _set_progress(self, done, total):
        try:
            self.progress.set((done / total) if total else 0)
            self.progress_label.configure(text=f"{done} / {total}")
        except Exception:
            pass

    # ── output helpers ───────────────────────────────────────────────────
    def _open_output(self):
        if self.last_output_dir and os.path.isdir(self.last_output_dir):
            open_in_explorer(self.last_output_dir)
        else:
            messagebox.showinfo(self.t("btn_open_folder", reshape=False), self.t("no_output_yet", reshape=False))

    def _save_log(self):
        content = self.log_box.get("0.0", "end").strip()
        target = self.last_output_dir if (self.last_output_dir and os.path.isdir(self.last_output_dir)) else os.path.expanduser("~")
        path = filedialog.asksaveasfilename(title=self.t("btn_save_log", reshape=False),
                                            defaultextension=".txt", initialfile="zoomtoolkit_log.txt",
                                            initialdir=target, filetypes=[("Text", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            self.log_message(self.t("log_saved", path))
        except Exception as e:
            self.log_message(self.t("log_save_err", e))

    def _autosave_log(self):
        d = self.last_output_dir
        if not d or not os.path.isdir(d):
            return
        try:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(d, f"zoomtoolkit_log_{stamp}.txt"), "w", encoding="utf-8") as f:
                f.write(self.log_box.get("0.0", "end").strip() + "\n")
        except Exception:
            pass

    # ── settings dialog ──────────────────────────────────────────────────
    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title(self.t("set_title", reshape=False))
        win.configure(fg_color=THEME["bg"])
        win.geometry("470x540")
        win.transient(self)
        win.grab_set()
        # CTkToplevel resets its icon after creation, so set the gear a tick later.
        win.after(220, lambda: self._set_window_icon(win, "settings_icon.ico"))
        pad = {"padx": 22}

        ctk.CTkLabel(win, text=self.t("set_formats"), font=self.font_label, text_color=THEME["text"]
                     ).pack(anchor=self.align("w"), pady=(22, 6), **pad)
        fmt_panel = ctk.CTkFrame(win, fg_color=THEME["panel"], corner_radius=10)
        fmt_panel.pack(fill="x", **pad)
        self._fmt_vars = {}
        for i, ext in enumerate(ALL_AUDIO_EXTS):
            var = tk.BooleanVar(value=ext in self.audio_exts)
            self._fmt_vars[ext] = var
            ctk.CTkCheckBox(fmt_panel, text=ext, variable=var, font=self.font_body, text_color=THEME["text"],
                            fg_color=THEME["amber"], hover_color=THEME["amber_hi"], border_color=THEME["line"],
                            checkmark_color=THEME["ink"], width=92, corner_radius=5
                            ).grid(row=i // 4, column=i % 4, sticky="w", padx=10, pady=8)

        ctk.CTkSwitch(win, text=self.t("set_recursive"), variable=self.recursive_var, font=self.font_body,
                      text_color=THEME["text"], progress_color=THEME["amber"], button_color=THEME["text"]
                      ).pack(anchor=self.align("w"), pady=(18, 6), **pad)

        ctk.CTkLabel(win, text=self.t("set_date_source"), font=self.font_label, text_color=THEME["text"]
                     ).pack(anchor=self.align("w"), pady=(14, 6), **pad)
        ds_map = {"modified": self.t("opt_date_modified", reshape=False),
                  "created": self.t("opt_date_created", reshape=False),
                  "metadata": self.t("opt_date_metadata", reshape=False)}
        ds_inv = {v: k for k, v in ds_map.items()}
        ds_menu = ctk.CTkOptionMenu(win, values=list(ds_map.values()), **self._option_kw())
        ds_menu.set(ds_map.get(self.date_source_var.get(), ds_map["modified"]))
        ds_menu.pack(fill="x", **pad)

        ctk.CTkLabel(win, text=self.t("set_about_body", APP_VERSION), font=self.font_caption,
                     text_color=THEME["muted"], justify="left").pack(anchor=self.align("w"), pady=(22, 4), **pad)
        on, off = self.t("set_on", reshape=False), self.t("set_off", reshape=False)
        libs = self.t("set_libs", on if HAS_HIJRI else off, on if HAS_DND else off,
                      on if 'File' in globals() else off)
        ctk.CTkLabel(win, text=libs, font=self.font_caption, text_color=THEME["faint"], justify="left"
                     ).pack(anchor=self.align("w"), pady=(0, 10), **pad)

        def save_close():
            chosen = [e for e in ALL_AUDIO_EXTS if self._fmt_vars[e].get()]
            self.audio_exts = chosen or list(DEFAULT_AUDIO_EXTS)
            self.date_source_var.set(ds_inv.get(ds_menu.get(), "modified"))
            self._save_settings()
            win.destroy()

        ctk.CTkButton(win, text=self.t("set_save"), command=save_close,
                      **self._primary_kw(THEME["amber"], THEME["amber_hi"], dark_text=True)
                      ).pack(fill="x", pady=(10, 22), **pad)

    def t(self, key, *args, reshape=True, **kwargs):
        text = TRANSLATIONS.get(self.lang_var.get(), TRANSLATIONS["English"]).get(key, key)
        if args or kwargs:
            try:
                text = text.format(*args, **kwargs)
            except Exception:
                pass
                
        if self.lang_var.get() == "العربية" and HAS_BIDI and reshape:
            if text is None: text = ""
            lines = str(text).split('\n')
            try:
                reshaped_lines = [arabic_reshaper.reshape(line) for line in lines]
                bidi_lines = [get_display(line) for line in reshaped_lines]
                return '\n'.join(bidi_lines)
            except Exception:
                pass
            
        return text

    def c(self, col, span=1, max_cols=3):
        return (max_cols - col - span) if self.lang_var.get() == "العربية" else col

    def align(self, align_str):
        if self.lang_var.get() != "العربية":
            return align_str
        mapping = {"w": "e", "e": "w", "nw": "ne", "ne": "nw", "sw": "se", "se": "sw"}
        return mapping.get(align_str, align_str)

    def change_language(self, new_lang):
        if self.main_container is not None:
            self.main_container.destroy()

        # Remember the current selections so they survive the language switch.
        # "Hijri" and "DD" are embedded in both languages' labels, so detection
        # works regardless of which language is active.
        ex_hijri = self._is_hijri(self.ex_calendar_vars.get())
        so_hijri = self._is_hijri(self.so_calendar_vars.get())
        ex_exact = "DD" in self.ex_format_vars.get()
        so_exact = "DD" in self.so_format_vars.get()

        cal_key = lambda hijri: "opt_hijri" if hijri else "opt_gregorian"
        fmt_key = lambda exact: "opt_fmt_exact" if exact else "opt_fmt_ym"

        self.ex_calendar_vars.set(self.t(cal_key(ex_hijri), reshape=False))
        self.so_calendar_vars.set(self.t(cal_key(so_hijri), reshape=False))
        self.ex_format_vars.set(self.t(fmt_key(ex_exact), reshape=False))
        self.so_format_vars.set(self.t(fmt_key(so_exact), reshape=False))
        self._build_ui()

    # ── type system ──────────────────────────────────────────────────────
    def _make_fonts(self, is_ar):
        # Bahnschrift reads like equipment labelling but can't shape Arabic,
        # so the Arabic build falls back to Segoe UI throughout.
        disp = "Segoe UI" if is_ar else "Bahnschrift SemiBold"
        eb   = "Segoe UI Semibold" if is_ar else "Bahnschrift SemiBold"
        mono = "Segoe UI" if is_ar else "Cascadia Mono"
        self.font_wordmark = ctk.CTkFont(family=disp, size=29, weight="bold" if is_ar else "normal")
        self.font_tab      = ctk.CTkFont(family=eb,   size=14)
        self.font_eyebrow  = ctk.CTkFont(family=eb,   size=12)
        self.font_body     = ctk.CTkFont(family="Segoe UI", size=14 if is_ar else 13)
        self.font_label    = ctk.CTkFont(family="Segoe UI Semibold", size=13)
        self.font_btn      = ctk.CTkFont(family=eb,   size=15)
        self.font_caption  = ctk.CTkFont(family="Segoe UI", size=12)
        self.font_log      = ctk.CTkFont(family=mono, size=13 if is_ar else 12)
        # aliases for any legacy references
        self.base_font, self.bold_font, self.title_font = self.font_body, self.font_btn, self.font_wordmark

    @staticmethod
    def _track(text):
        # Faux letter-spacing for tracked caps (tk has no letter-spacing).
        return " ".join(text)

    # ── reusable widget styling ──────────────────────────────────────────
    def _entry_kw(self):
        return dict(fg_color=THEME["well"], border_color=THEME["well_bd"], border_width=1,
                    corner_radius=9, text_color=THEME["text"], font=self.font_body, height=38)

    def _browse_kw(self):
        return dict(fg_color="transparent", border_color=THEME["line"], border_width=1,
                    hover_color=THEME["line_soft"], text_color=THEME["muted"],
                    corner_radius=9, height=38, width=96, font=self.font_label)

    def _option_kw(self):
        return dict(fg_color=THEME["well"], button_color=THEME["line"],
                    button_hover_color=THEME["line_soft"], text_color=THEME["text"],
                    dropdown_fg_color=THEME["panel_2"], dropdown_hover_color=THEME["line"],
                    dropdown_text_color=THEME["text"], corner_radius=9, height=38,
                    font=self.font_body, dropdown_font=self.font_body)

    def _primary_kw(self, color, hover, dark_text=False):
        return dict(fg_color=color, hover_color=hover,
                    text_color=THEME["ink"] if dark_text else THEME["text"],
                    corner_radius=11, height=48, font=self.font_btn)

    def _set_status(self, working):
        if not hasattr(self, "status_label"):
            return
        is_ar = self.lang_var.get() == "العربية"
        key = "status_working" if working else "status_ready"
        label = self.t(key) if is_ar else "●  " + self.t(key, reshape=False)
        self.status_label.configure(text=label,
                                    text_color=THEME["amber"] if working else THEME["green"])

    def _section_header(self, tab, tab_key, desc_key, is_ar):
        head = ctk.CTkFrame(tab, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=3, sticky="ew", padx=18, pady=(18, 2))
        side = "right" if is_ar else "left"
        tick = ctk.CTkFrame(head, width=4, height=16, fg_color=THEME["amber"], corner_radius=2)
        tick.pack(side=side, padx=(10, 0) if is_ar else (0, 10))
        eyebrow = self.t(tab_key) if is_ar else self._track(TRANSLATIONS["English"][tab_key].upper())
        ctk.CTkLabel(head, text=eyebrow, font=self.font_eyebrow, text_color=THEME["amber"]).pack(side=side)
        ctk.CTkLabel(tab, text=self.t(desc_key), font=self.font_caption, text_color=THEME["muted"],
                     justify="right" if is_ar else "left", wraplength=760
                     ).grid(row=1, column=0, columnspan=3, padx=18, pady=(4, 14), sticky=self.align("w"))

    # ── layout ───────────────────────────────────────────────────────────
    def _build_ui(self):
        self.title(self.t("title", reshape=False))
        is_ar = self.lang_var.get() == "العربية"
        self._make_fonts(is_ar)

        self.main_container = ctk.CTkFrame(self, fg_color=THEME["bg"])
        self.main_container.pack(fill="both", expand=True)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=1, minsize=190)

        self._build_header(is_ar)

        self.tabview = ctk.CTkTabview(
            self.main_container, fg_color=THEME["panel"], corner_radius=14,
            segmented_button_fg_color=THEME["well"],
            segmented_button_selected_color=THEME["amber_deep"],
            segmented_button_selected_hover_color=THEME["amber"],
            segmented_button_unselected_color=THEME["well"],
            segmented_button_unselected_hover_color=THEME["line_soft"],
            text_color=THEME["text"], text_color_disabled=THEME["faint"],
        )
        self.tabview.grid(row=1, column=0, padx=22, pady=(2, 12), sticky="ew")

        self.tab_names = {
            "ex": self.t("tab_extractor"),
            "cl": self.t("tab_cleaner"),
            "so": self.t("tab_sorter"),
        }
        order = ["so", "cl", "ex"] if is_ar else ["ex", "cl", "so"]
        for key in order:
            self.tabview.add(self.tab_names[key])
        self.tabview.set(self.tab_names["ex"])

        # No public API exists in CTk 5.2.2 to set the segmented-button font,
        # so this one internal access stays — guarded so a future version that
        # renames the attribute degrades gracefully instead of crashing.
        try:
            self.tabview._segmented_button.configure(font=self.font_tab, height=42)
        except Exception:
            pass

        self._build_extractor_tab()
        self._build_cleaner_tab()
        self._build_sorter_tab()
        self._build_log(is_ar)

    def _build_header(self, is_ar):
        header = ctk.CTkFrame(self.main_container, fg_color=THEME["panel"], corner_radius=14)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 8))
        header.grid_columnconfigure(self.c(0, max_cols=2), weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=self.c(0, max_cols=2), sticky=self.align("w"), padx=24, pady=20)
        self.title_label = ctk.CTkLabel(left, text=self.t("title"), font=self.font_wordmark,
                                        text_color=THEME["text"])
        self.title_label.pack(anchor=self.align("w"))
        sub = self.t("subtitle") if is_ar else self._track(TRANSLATIONS["English"]["subtitle"])
        ctk.CTkLabel(left, text=sub, font=self.font_eyebrow, text_color=THEME["amber"]
                     ).pack(anchor=self.align("w"), pady=(3, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=self.c(1, max_cols=2), sticky=self.align("e"), padx=24, pady=20)

        toprow = ctk.CTkFrame(right, fg_color="transparent")
        toprow.pack(anchor=self.align("e"))
        self.btn_settings = ctk.CTkButton(toprow, text=self.t("btn_settings"), command=self._open_settings,
                                          fg_color="transparent", border_color=THEME["line"], border_width=1,
                                          hover_color=THEME["line_soft"], text_color=THEME["muted"],
                                          corner_radius=9, height=38, width=112, font=self.font_label)
        self.lang_menu = ctk.CTkOptionMenu(toprow, variable=self.lang_var, values=["English", "العربية"],
                                           command=self.change_language, width=128, **self._option_kw())
        self.lang_menu.pack(side="right")
        self.btn_settings.pack(side="right", padx=(0, 8))

        self.status_label = ctk.CTkLabel(right, text="", font=self.font_eyebrow, text_color=THEME["green"])
        self.status_label.pack(anchor=self.align("e"), pady=(12, 3))
        self.meter = LevelMeter(right, width=214, height=26)
        self.meter.pack(anchor=self.align("e"))
        self._set_status(False)

    def _build_log(self, is_ar):
        panel = ctk.CTkFrame(self.main_container, fg_color=THEME["panel"], corner_radius=14)
        panel.grid(row=2, column=0, sticky="nsew", padx=22, pady=(8, 20))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        bar = ctk.CTkFrame(panel, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 2))
        side = "right" if is_ar else "left"
        self._ctrl_side = "left" if is_ar else "right"
        dot = ctk.CTkFrame(bar, width=8, height=8, corner_radius=4, fg_color=THEME["amber"])
        dot.pack(side=side, padx=(8, 0) if is_ar else (0, 9))
        label = self.t("console") if is_ar else self._track("CONSOLE")
        ctk.CTkLabel(bar, text=label, font=self.font_eyebrow, text_color=THEME["muted"]).pack(side=side)

        outline = dict(fg_color="transparent", border_color=THEME["line"], border_width=1,
                       hover_color=THEME["line_soft"], text_color=THEME["muted"], corner_radius=8,
                       height=30, font=self.font_caption)
        self.btn_open = ctk.CTkButton(bar, text=self.t("btn_open_folder"), command=self._open_output, width=108, **outline)
        self.btn_savelog = ctk.CTkButton(bar, text=self.t("btn_save_log"), command=self._save_log, width=94, **outline)
        self.progress_label = ctk.CTkLabel(bar, text="", font=self.font_caption, text_color=THEME["amber"])
        self.btn_stop = ctk.CTkButton(bar, text=self.t("btn_stop"), command=self._request_cancel, width=74,
                                      fg_color="transparent", border_color=THEME["red"], border_width=1,
                                      hover_color=THEME["line_soft"], text_color=THEME["red"],
                                      corner_radius=8, height=30, font=self.font_caption)
        self.btn_open.pack(side=self._ctrl_side)
        self.btn_savelog.pack(side=self._ctrl_side, padx=8)
        self.progress_label.pack(side=self._ctrl_side, padx=(8, 0))
        self.btn_stop.pack(side=self._ctrl_side, padx=8)
        self.btn_stop.pack_forget()

        self.progress = ctk.CTkProgressBar(panel, mode="determinate", height=6, corner_radius=3,
                                           progress_color=THEME["amber"], fg_color=THEME["well"])
        self.progress.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 2))
        self.progress.set(0)
        self.progress.grid_remove()

        self.log_box = ctk.CTkTextbox(panel, wrap="word", font=self.font_log,
                                      fg_color=THEME["well"], text_color=THEME["text"],
                                      border_width=0, corner_radius=10,
                                      scrollbar_button_color=THEME["line"],
                                      scrollbar_button_hover_color=THEME["line_soft"])
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(2, 16))
        self.log_box.insert("0.0", self.t("msg_welcome"))
        self.log_box.configure(state="disabled")

    def _build_extractor_tab(self):
        is_ar = self.lang_var.get() == "العربية"
        tab = self.tabview.tab(self.tab_names["ex"])
        for i in range(3):
            tab.grid_columnconfigure(i, weight=1 if i == self.c(1) else 0)

        self._section_header(tab, "tab_extractor", "desc_extractor", is_ar)

        self.lbl_ex_source = ctk.CTkLabel(tab, text=self.t("lbl_source"), width=112, anchor=self.align("w"),
                                          font=self.font_label, text_color=THEME["text"])
        self.lbl_ex_source.grid(row=2, column=self.c(0), padx=(18, 8), pady=9, sticky=self.align("w"))
        self.entry_ex_source = ctk.CTkEntry(tab, textvariable=self.ex_source_path, state="readonly",
                                            placeholder_text="—", **self._entry_kw())
        self.entry_ex_source.grid(row=2, column=self.c(1), padx=8, pady=9, sticky="ew")
        self._enable_dnd(self.entry_ex_source, self.ex_source_path)
        self.btn_ex_source = ctk.CTkButton(tab, text=self.t("btn_browse"), command=self.browse_ex_source, **self._browse_kw())
        self.btn_ex_source.grid(row=2, column=self.c(2), padx=(8, 18), pady=9)

        self.lbl_ex_dest = ctk.CTkLabel(tab, text=self.t("lbl_dest"), width=112, anchor=self.align("w"),
                                        font=self.font_label, text_color=THEME["text"])
        self.lbl_ex_dest.grid(row=3, column=self.c(0), padx=(18, 8), pady=9, sticky=self.align("w"))
        self.entry_ex_dest = ctk.CTkEntry(tab, textvariable=self.ex_dest_path, state="readonly",
                                          placeholder_text="—", **self._entry_kw())
        self.entry_ex_dest.grid(row=3, column=self.c(1), padx=8, pady=9, sticky="ew")
        self._enable_dnd(self.entry_ex_dest, self.ex_dest_path)
        self.btn_ex_dest = ctk.CTkButton(tab, text=self.t("btn_browse"), command=self.browse_ex_dest, **self._browse_kw())
        self.btn_ex_dest.grid(row=3, column=self.c(2), padx=(8, 18), pady=9)

        self.chk_ex_sort = ctk.CTkCheckBox(tab, text=self.t("chk_auto_sort"), variable=self.ex_auto_sort_var,
                                           font=self.font_body, text_color=THEME["text"],
                                           fg_color=THEME["amber"], hover_color=THEME["amber_hi"],
                                           border_color=THEME["line"], checkmark_color=THEME["ink"], corner_radius=5)
        self.chk_ex_sort.grid(row=4, column=self.c(0), padx=(18, 8), pady=(16, 10), sticky=self.align("w"))
        self.opt_ex_cal = ctk.CTkOptionMenu(tab, variable=self.ex_calendar_vars,
                                            values=[self.t("opt_gregorian", reshape=False), self.t("opt_hijri", reshape=False)],
                                            width=118, **self._option_kw())
        self.opt_ex_cal.grid(row=4, column=self.c(1), padx=8, pady=(16, 10), sticky=self.align("e"))
        self.opt_ex_format = ctk.CTkOptionMenu(tab, variable=self.ex_format_vars,
                                               values=[self.t("opt_fmt_ym", reshape=False), self.t("opt_fmt_exact", reshape=False)],
                                               **self._option_kw())
        self.opt_ex_format.grid(row=4, column=self.c(2), padx=(8, 18), pady=(16, 10), sticky="ew")

        self.btn_extract = ctk.CTkButton(tab, text=self.t("btn_extract"), command=self.start_extraction_thread,
                                         **self._primary_kw(THEME["amber"], THEME["amber_hi"], dark_text=True))
        self.btn_extract.grid(row=5, column=0, columnspan=3, padx=18, pady=(18, 20), sticky="ew")

    def _build_cleaner_tab(self):
        is_ar = self.lang_var.get() == "العربية"
        tab = self.tabview.tab(self.tab_names["cl"])
        for i in range(3):
            tab.grid_columnconfigure(i, weight=1 if i == self.c(1) else 0)

        self._section_header(tab, "tab_cleaner", "desc_cleaner", is_ar)

        self.lbl_cl_target = ctk.CTkLabel(tab, text=self.t("lbl_target"), width=112, anchor=self.align("w"),
                                          font=self.font_label, text_color=THEME["text"])
        self.lbl_cl_target.grid(row=2, column=self.c(0), padx=(18, 8), pady=9, sticky=self.align("w"))
        self.entry_cl_target = ctk.CTkEntry(tab, textvariable=self.cl_target_path, state="readonly",
                                            placeholder_text="—", **self._entry_kw())
        self.entry_cl_target.grid(row=2, column=self.c(1), padx=8, pady=9, sticky="ew")
        self._enable_dnd(self.entry_cl_target, self.cl_target_path)
        self.btn_cl_target = ctk.CTkButton(tab, text=self.t("btn_browse"), command=self.browse_cl_target, **self._browse_kw())
        self.btn_cl_target.grid(row=2, column=self.c(2), padx=(8, 18), pady=9)

        self.lbl_cl_thresh = ctk.CTkLabel(tab, text=self.t("lbl_thresh"), width=112, anchor=self.align("w"),
                                          font=self.font_label, text_color=THEME["text"])
        self.lbl_cl_thresh.grid(row=3, column=self.c(0), padx=(18, 8), pady=9, sticky=self.align("w"))
        self.entry_thresh = ctk.CTkEntry(tab, textvariable=self.cl_threshold, **self._entry_kw())
        self.entry_thresh.grid(row=3, column=self.c(1, span=2), columnspan=2, padx=(8, 18), pady=9, sticky="ew")

        self.chk_cl_preview = ctk.CTkCheckBox(tab, text=self.t("chk_preview"), variable=self.cl_preview_var,
                                              font=self.font_body, text_color=THEME["muted"],
                                              fg_color=THEME["amber"], hover_color=THEME["amber_hi"],
                                              border_color=THEME["line"], checkmark_color=THEME["ink"], corner_radius=5)
        self.chk_cl_preview.grid(row=4, column=self.c(0), columnspan=3, padx=18, pady=(14, 6), sticky=self.align("w"))

        self.btn_clean = ctk.CTkButton(tab, text=self.t("btn_clean"), command=self.start_cleaner_thread,
                                       **self._primary_kw(THEME["red"], THEME["red_hi"]))
        self.btn_clean.grid(row=5, column=0, columnspan=3, padx=18, pady=(8, 20), sticky="ew")

    def _build_sorter_tab(self):
        is_ar = self.lang_var.get() == "العربية"
        tab = self.tabview.tab(self.tab_names["so"])
        for i in range(3):
            tab.grid_columnconfigure(i, weight=1 if i == self.c(1) else 0)

        self._section_header(tab, "tab_sorter", "desc_sorter", is_ar)

        self.lbl_so_source = ctk.CTkLabel(tab, text=self.t("lbl_source"), width=112, anchor=self.align("w"),
                                          font=self.font_label, text_color=THEME["text"])
        self.lbl_so_source.grid(row=2, column=self.c(0), padx=(18, 8), pady=9, sticky=self.align("w"))
        self.entry_so_source = ctk.CTkEntry(tab, textvariable=self.so_source_path, state="readonly",
                                            placeholder_text="—", **self._entry_kw())
        self.entry_so_source.grid(row=2, column=self.c(1), padx=8, pady=9, sticky="ew")
        self._enable_dnd(self.entry_so_source, self.so_source_path)
        self.btn_so_source = ctk.CTkButton(tab, text=self.t("btn_browse"), command=self.browse_so_source, **self._browse_kw())
        self.btn_so_source.grid(row=2, column=self.c(2), padx=(8, 18), pady=9)

        self.lbl_so_format = ctk.CTkLabel(tab, text=self.t("lbl_cal_format"), width=112, anchor=self.align("w"),
                                          font=self.font_label, text_color=THEME["text"])
        self.lbl_so_format.grid(row=3, column=self.c(0), padx=(18, 8), pady=(16, 10), sticky=self.align("w"))
        self.opt_so_cal = ctk.CTkOptionMenu(tab, variable=self.so_calendar_vars,
                                            values=[self.t("opt_gregorian", reshape=False), self.t("opt_hijri", reshape=False)],
                                            width=118, **self._option_kw())
        self.opt_so_cal.grid(row=3, column=self.c(1), padx=8, pady=(16, 10), sticky=self.align("e"))
        self.opt_so_format = ctk.CTkOptionMenu(tab, variable=self.so_format_vars,
                                               values=[self.t("opt_fmt_ym", reshape=False), self.t("opt_fmt_exact", reshape=False)],
                                               **self._option_kw())
        self.opt_so_format.grid(row=3, column=self.c(2), padx=(8, 18), pady=(16, 10), sticky="ew")

        self.chk_so_preview = ctk.CTkCheckBox(tab, text=self.t("chk_preview"), variable=self.so_preview_var,
                                              font=self.font_body, text_color=THEME["muted"],
                                              fg_color=THEME["amber"], hover_color=THEME["amber_hi"],
                                              border_color=THEME["line"], checkmark_color=THEME["ink"], corner_radius=5)
        self.chk_so_preview.grid(row=4, column=self.c(0), columnspan=3, padx=18, pady=(14, 6), sticky=self.align("w"))

        self.btn_sort = ctk.CTkButton(tab, text=self.t("btn_sort"), command=self.start_sorter_thread,
                                      **self._primary_kw(THEME["green"], THEME["green_hi"]))
        self.btn_sort.grid(row=5, column=0, columnspan=3, padx=18, pady=(8, 20), sticky="ew")

    def log_message(self, message: str):
        self.after(0, self._append_to_log, message)

    def _append_to_log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_ui_state(self, state):
        mode = "normal" if state == "normal" else "disabled"
        for name in ("btn_ex_source", "btn_ex_dest", "chk_ex_sort", "btn_extract",
                     "btn_cl_target", "btn_clean", "chk_cl_preview", "btn_so_source",
                     "btn_sort", "chk_so_preview", "lang_menu", "btn_settings",
                     "opt_ex_cal", "opt_ex_format", "opt_so_cal", "opt_so_format", "entry_thresh"):
            widget = getattr(self, name, None)
            if widget is not None:
                try:
                    widget.configure(state=mode)
                except Exception:
                    pass

    def worker_finished(self, msg_title_raw, msg_body_raw, error=False):
        try:
            self.meter.stop()
            self._set_status(False)
            self.progress.grid_remove()
            self.btn_stop.pack_forget()
            self.set_ui_state("normal")
            if self.last_output_dir and os.path.isdir(self.last_output_dir):
                self.btn_open.configure(state="normal")
        except Exception:
            pass

        reshaped_body = self.t(msg_body_raw) if msg_body_raw in TRANSLATIONS["English"] else msg_body_raw
        if self.lang_var.get() == "العربية" and HAS_BIDI:
            try:
                reshaped_body = '\n'.join([get_display(arabic_reshaper.reshape(ln)) for ln in str(msg_body_raw).split('\n')])
            except Exception: pass

        self.log_message(f"{'-'*30}\n{reshaped_body}")
        self._autosave_log()

        if error:
            messagebox.showerror(msg_title_raw, msg_body_raw)
        else:
            messagebox.showinfo(msg_title_raw, msg_body_raw)

    def _is_hijri(self, calendar_type):
        return "Hijri" in calendar_type

    def _get_formatted_date(self, dt, format_val, calendar_type):
        if self._is_hijri(calendar_type):
            try:
                Gregorian = hijri_gregorian_cls()
                hijri_date = Gregorian(dt.year, dt.month, dt.day).to_hijri()
                hj_year = hijri_date.year
                hj_month = f"{hijri_date.month:02d}"
                hj_day = f"{hijri_date.day:02d}"
                
                if "YYYY-MM" in format_val and "DD" not in format_val:
                    return f"{hj_year}-{hj_month}"
                else:
                    return f"{hj_year}-{hj_month}-{hj_day}"
            except ImportError:
                return self.t("err_hijri_missing", reshape=False)
        else:
            date_format = "%Y-%m" if "YYYY-MM" in format_val and "DD" not in format_val else "%Y-%m-%d"
            return dt.strftime(date_format)

    def _sort_files(self, base_dir, paths, format_val, calendar_type, preview=False, progress=False):
        """Move each audio file in `paths` (absolute) into a date-based subfolder
        of `base_dir`. Honours cancel/preview/progress. Returns the count handled."""
        base = Path(base_dir)
        moved_count = 0
        total = len(paths)
        for idx, filepath in enumerate(paths, 1):
            if self.cancel_event.is_set():
                break
            filepath = Path(filepath)
            try:
                if not filepath.is_file():
                    continue
                dt = self._file_dt(filepath)
                folder_name = self._get_formatted_date(dt, format_val, calendar_type)
                dest_folder = base / folder_name

                if filepath.parent == dest_folder:      # already in the right place
                    continue
                if preview:
                    self.log_message(self.t("log_preview", filepath.name, folder_name + "/"))
                else:
                    dest_folder.mkdir(exist_ok=True)
                    target = unique_destination(dest_folder, filepath.name)
                    self.log_message(self.t("log_sorted", filepath.name, folder_name))
                    shutil.move(str(filepath), str(target))
                moved_count += 1
            except Exception as e:
                self.log_message(self.t("log_err_copy", filepath.name, e))
            if progress:
                self.after(0, self._set_progress, idx, total)
        return moved_count

    def browse_ex_source(self):
        folder = filedialog.askdirectory(title=self.t("lbl_source", reshape=False))
        if folder: self.ex_source_path.set(folder)

    def browse_ex_dest(self):
        folder = filedialog.askdirectory(title=self.t("lbl_dest", reshape=False))
        if folder: self.ex_dest_path.set(folder)

    def start_extraction_thread(self):
        source = self.ex_source_path.get()
        dest = self.ex_dest_path.get()
        if not source or not dest:
            messagebox.showwarning(self.t("err_missing", reshape=False), self.t("err_missing_ex", reshape=False))
            return
        if self.ex_auto_sort_var.get() and self._is_hijri(self.ex_calendar_vars.get()) and not HAS_HIJRI:
            messagebox.showwarning(self.t("err_dep_req", reshape=False), self.t("err_dep_hijri", reshape=False))
            return

        self.last_output_dir = dest
        self._begin_job()
        self.log_message(self.t("log_starting_ex", source, dest))
        threading.Thread(target=self.extract_zoom_files_worker,
                         args=(source, dest, self.ex_auto_sort_var.get(),
                               self.ex_format_vars.get(), self.ex_calendar_vars.get()),
                         daemon=True).start()

    def extract_zoom_files_worker(self, sd_card_path, destination_path, auto_sort, format_val, calendar_type):
        try:
            source = Path(sd_card_path).resolve()
            dest = Path(destination_path).resolve()

            if dest == source or source in dest.parents:
                self.after(0, self.worker_finished, self.t("error", reshape=False), self.t("err_dest_in_source", reshape=False), True)
                return

            dest.mkdir(parents=True, exist_ok=True)
            self.log_message(self.t("log_scanning", sd_card_path))

            all_files = [p for p in source.rglob('*')
                         if p.is_file() and p.suffix.lower() in self.audio_exts]
            total = len(all_files)
            copied_count = 0
            copied_paths = []

            for idx, file_path in enumerate(all_files, 1):
                if self.cancel_event.is_set():
                    break
                parent_folder_name = file_path.parent.name
                if parent_folder_name.upper().startswith('FOLDER'):
                    new_file_name = f"{file_path.stem}_{parent_folder_name}{file_path.suffix}"
                else:
                    new_file_name = file_path.name

                dest_file_path = unique_destination(dest, new_file_name)
                try:
                    self.log_message(self.t("log_copying", file_path.name, dest_file_path.name))
                    shutil.copy2(file_path, dest_file_path)
                    copied_count += 1
                    copied_paths.append(dest_file_path)
                except Exception as e:
                    self.log_message(self.t("log_err_copy", file_path.name, e))
                self.after(0, self._set_progress, idx, total)

            if auto_sort and copied_count > 0 and not self.cancel_event.is_set():
                self.log_message(self.t("log_auto_sorting"))
                # Only sort the files we just copied, not anything already in dest.
                self._sort_files(dest, copied_paths, format_val, calendar_type)

            if self.cancel_event.is_set():
                self.after(0, self.worker_finished, self.t("done_stopped", reshape=False), self.t("done_stopped_msg", copied_count, reshape=False))
            else:
                self.after(0, self.worker_finished, self.t("done_ex", reshape=False), self.t("done_ex_msg", copied_count, reshape=False))
        except Exception as e:
            self.after(0, self.worker_finished, self.t("error", reshape=False), str(e), True)

    def browse_cl_target(self):
        folder = filedialog.askdirectory(title=self.t("lbl_target", reshape=False))
        if folder: self.cl_target_path.set(folder)

    def start_cleaner_thread(self):
        target = self.cl_target_path.get()
        threshold_str = self.cl_threshold.get()
        if not target:
            messagebox.showwarning(self.t("err_missing", reshape=False), self.t("err_missing_cl", reshape=False))
            return

        try:
            threshold = float(threshold_str)
            if threshold <= 0: raise ValueError
        except ValueError:
            messagebox.showwarning(self.t("err_missing", reshape=False), self.t("err_invalid_thresh", reshape=False))
            return

        preview = bool(self.cl_preview_var.get())
        if not preview:
            confirm = messagebox.askyesno(self.t("warn_title", reshape=False),
                                          self.t("warn_clean", threshold, target, reshape=False))
            if not confirm:
                self.log_message(self.t("log_cancelled"))
                return

        self.last_output_dir = target
        self._begin_job()
        self.log_message(self.t("log_starting_cl", target, threshold))
        threading.Thread(target=self.clean_audio_worker, args=(target, threshold, preview), daemon=True).start()

    def clean_audio_worker(self, target_directory, threshold_seconds, preview):
        try:
            if 'File' not in globals():
                self.after(0, self.worker_finished, self.t("err_dep_req", reshape=False), self.t("err_dep_mutagen", reshape=False), True)
                return

            files = self._iter_audio(target_directory, self.recursive_var.get())
            total = len(files)
            moved_count = 0
            dest_folder = os.path.join(target_directory, "short_audio")
            created_dest = False

            for idx, filepath in enumerate(files, 1):
                if self.cancel_event.is_set():
                    break
                try:
                    audio = File(str(filepath))
                    if audio is not None and audio.info is not None:
                        duration = audio.info.length
                        if duration < threshold_seconds:
                            if preview:
                                self.log_message(self.t("log_preview", filepath.name, "short_audio/"))
                                moved_count += 1
                            else:
                                if not created_dest:
                                    os.makedirs(dest_folder, exist_ok=True)
                                    created_dest = True
                                target = unique_destination(dest_folder, filepath.name)
                                self.log_message(self.t("log_moved", filepath.name, duration))
                                shutil.move(str(filepath), str(target))
                                moved_count += 1
                except Exception as e:
                    self.log_message(self.t("log_err_copy", filepath.name, e))
                self.after(0, self._set_progress, idx, total)

            if self.cancel_event.is_set():
                self.after(0, self.worker_finished, self.t("done_stopped", reshape=False), self.t("done_stopped_msg", moved_count, reshape=False))
            elif preview:
                self.after(0, self.worker_finished, self.t("done_preview", reshape=False), self.t("done_preview_msg", moved_count, reshape=False))
            else:
                self.after(0, self.worker_finished, self.t("done_cl", reshape=False), self.t("done_cl_msg", moved_count, reshape=False))
        except Exception as e:
            self.after(0, self.worker_finished, self.t("error", reshape=False), str(e), True)

    def browse_so_source(self):
        folder = filedialog.askdirectory(title=self.t("lbl_source", reshape=False))
        if folder: self.so_source_path.set(folder)

    def start_sorter_thread(self):
        source = self.so_source_path.get()
        format_val = self.so_format_vars.get()
        calendar_type = self.so_calendar_vars.get()
        if not source:
            messagebox.showwarning(self.t("err_missing", reshape=False), self.t("err_missing_so", reshape=False))
            return
        if self._is_hijri(calendar_type) and not HAS_HIJRI:
            messagebox.showwarning(self.t("err_dep_req", reshape=False), self.t("err_dep_hijri", reshape=False))
            return

        paths = self._iter_audio(source, self.recursive_var.get())
        preview = bool(self.so_preview_var.get())
        if not preview:
            # Build a quick plan so the confirm dialog shows exactly what will happen.
            plan = {}
            for p in paths:
                try:
                    name = self._get_formatted_date(self._file_dt(p), format_val, calendar_type)
                except Exception:
                    name = "?"
                plan[name] = plan.get(name, 0) + 1
            shown = sorted(plan.items())
            lines = "\n".join(f"   {k}/   ({v})" for k, v in shown[:12])
            if len(shown) > 12:
                lines += "\n   …"
            msg = self.t("confirm_sort_plan", len(paths), len(plan), lines)
            if not messagebox.askyesno(self.t("warn_title", reshape=False), msg):
                self.log_message(self.t("log_cancelled"))
                return

        self.last_output_dir = source
        self._begin_job()
        self.log_message(self.t("log_starting_so", source, calendar_type, format_val))
        threading.Thread(target=self.auto_sort_worker,
                         args=(source, paths, format_val, calendar_type, preview), daemon=True).start()

    def auto_sort_worker(self, target_directory, paths, format_val, calendar_type, preview):
        try:
            moved_count = self._sort_files(target_directory, paths, format_val, calendar_type,
                                           preview=preview, progress=True)
            if self.cancel_event.is_set():
                self.after(0, self.worker_finished, self.t("done_stopped", reshape=False), self.t("done_stopped_msg", moved_count, reshape=False))
            elif preview:
                self.after(0, self.worker_finished, self.t("done_preview", reshape=False), self.t("done_preview_msg", moved_count, reshape=False))
            else:
                self.after(0, self.worker_finished, self.t("done_so", reshape=False), self.t("done_so_msg", moved_count, reshape=False))
        except Exception as e:
            self.after(0, self.worker_finished, self.t("error", reshape=False), str(e), True)

if __name__ == "__main__":
    app = ZoomToolkitApp()
    app.mainloop()