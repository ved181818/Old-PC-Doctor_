# Old PC Doctor - Version 1.0
# Lightweight Windows system information and safety checker.
# Compatible target: Windows 7 + Python 3.8 (standard library only).
# This program does NOT modify the registry, disable startup items, or delete files.

import os
import sys
import platform
import ctypes
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

APP_TITLE = "Old PC Doctor"
BG = "#101923"
PANEL = "#172635"
TEXT = "#e5edf3"
MUTED = "#a9bdca"
ACCENT = "#54c7ef"
GOOD = "#68d69a"
WARN = "#f0c36a"
BAD = "#ef8585"


def get_memory_info():
    """Return total and available physical memory in bytes, or (None, None)."""
    if os.name != "nt":
        return None, None
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    try:
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys), int(status.ullAvailPhys)
    except Exception:
        pass
    return None, None


def get_uptime():
    if os.name == "nt":
        try:
            seconds = int(ctypes.windll.kernel32.GetTickCount64() / 1000)
            days, rem = divmod(seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes = rem // 60
            return "{} days, {} hours, {} minutes".format(days, hours, minutes)
        except Exception:
            return "Unavailable"
    return "Unavailable"


def get_windows_version():
    try:
        return "{} ({})".format(platform.platform(), platform.architecture()[0])
    except Exception:
        return platform.platform()


def get_cpu_name():
    name = platform.processor().strip()
    if name:
        return name
    return os.environ.get("PROCESSOR_IDENTIFIER", "Not reported by Windows")


def get_drives():
    drives = []
    if os.name == "nt":
        try:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    root = "{}:\\".format(chr(65 + i))
                    try:
                        usage = shutil.disk_usage(root)
                        drives.append((root, usage.total, usage.used, usage.free))
                    except Exception:
                        pass
        except Exception:
            pass
    else:
        try:
            usage = shutil.disk_usage(os.path.abspath(os.sep))
            drives.append((os.path.abspath(os.sep), usage.total, usage.used, usage.free))
        except Exception:
            pass
    return drives


def read_startup_entries():
    """Read Run keys only. No registry values are changed."""
    entries = []
    if os.name != "nt":
        return entries
    try:
        import winreg
    except Exception:
        return entries

    locations = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "Current user"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "All users"),
    ]
    for hive, subkey, scope in locations:
        try:
            key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
            index = 0
            while True:
                try:
                    name, value, _kind = winreg.EnumValue(key, index)
                    entries.append((scope, name, str(value)))
                    index += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except OSError:
            continue
    return entries


def human_bytes(value):
    if value is None:
        return "Unavailable"
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return "{:.1f} {}".format(amount, unit)
        amount /= 1024.0


class OldPCDoctor:
    def __init__(self, root):
        self.root = root
        self.root.title("Old PC Doctor - Lightweight System Checker")
        self.root.geometry("900x650")
        self.root.minsize(740, 540)
        self.root.configure(bg=BG)

        self.report_text = ""
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self.root, bg=PANEL, padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="OLD PC DOCTOR", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 19, "bold")).pack(side="left")
        tk.Label(header, text="LIGHTWEIGHT SYSTEM CHECKER",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(
                     side="left", padx=14, pady=(7, 0))
        tk.Label(header, text="V1.0  |  READ-ONLY",
                 bg=PANEL, fg=GOOD, font=("Segoe UI", 9, "bold")).pack(side="right")

        bar = tk.Frame(self.root, bg=BG, padx=16, pady=10)
        bar.pack(fill="x")
        tk.Button(bar, text="SCAN / REFRESH", command=self.refresh,
                  bg="#087fa8", fg="white", relief="flat",
                  padx=14, pady=8, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(bar, text="VIEW STARTUP ITEMS", command=self.show_startup,
                  bg="#34495b", fg="white", relief="flat",
                  padx=14, pady=8).pack(side="left", padx=8)
        tk.Button(bar, text="EXPORT REPORT", command=self.export_report,
                  bg="#176b4a", fg="white", relief="flat",
                  padx=14, pady=8).pack(side="right")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8))

        self.overview_tab = tk.Frame(self.notebook, bg=BG, padx=16, pady=14)
        self.drives_tab = tk.Frame(self.notebook, bg=BG, padx=16, pady=14)
        self.advice_tab = tk.Frame(self.notebook, bg=BG, padx=16, pady=14)
        self.notebook.add(self.overview_tab, text="Overview")
        self.notebook.add(self.drives_tab, text="Storage")
        self.notebook.add(self.advice_tab, text="Advice")

        self.overview = tk.Text(self.overview_tab, bg="#0b121a", fg=TEXT,
                                insertbackground="white", relief="flat",
                                font=("Consolas", 10), wrap="word",
                                padx=14, pady=12, state="disabled")
        self.overview.pack(fill="both", expand=True)

        self.drives = tk.Text(self.drives_tab, bg="#0b121a", fg=TEXT,
                              insertbackground="white", relief="flat",
                              font=("Consolas", 10), wrap="word",
                              padx=14, pady=12, state="disabled")
        self.drives.pack(fill="both", expand=True)

        self.advice = tk.Text(self.advice_tab, bg="#0b121a", fg=TEXT,
                              insertbackground="white", relief="flat",
                              font=("Segoe UI", 10), wrap="word",
                              padx=14, pady=12, state="disabled")
        self.advice.pack(fill="both", expand=True)

        footer = tk.Label(
            self.root,
            text="Safety: this version only reads system information. It does not clean, disable, or repair anything.",
            bg=BG, fg=MUTED, font=("Segoe UI", 8)
        )
        footer.pack(fill="x", padx=18, pady=(0, 10))

    def _set_text(self, widget, content):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def refresh(self):
        total, available = get_memory_info()
        drives = get_drives()
        cpu_count = os.cpu_count() or "Unknown"
        cpu_name = get_cpu_name()
        windows = get_windows_version()
        uptime = get_uptime()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if total:
            used = total - available
            memory_line = (
                "Physical RAM:  {}\n"
                "RAM in use:    {} ({:.0f}%)\n"
                "RAM available: {}\n"
            ).format(human_bytes(total), human_bytes(used),
                     (used / total * 100.0) if total else 0,
                     human_bytes(available))
            ram_percent = used / total * 100.0
        else:
            memory_line = "Physical RAM:  Could not read memory information.\n"
            ram_percent = None

        overview = (
            "SYSTEM OVERVIEW\n"
            "============================================================\n"
            "Scan time:       {now}\n"
            "Computer name:   {computer}\n"
            "Windows:         {windows}\n"
            "Processor:       {cpu}\n"
            "Logical CPUs:    {cores}\n"
            "System uptime:   {uptime}\n\n"
            "{memory}"
            "Python:          {python}\n"
            "Program path:    {path}\n\n"
            "IMPORTANT\n"
            "This is an information checker, not a certified hardware test.\n"
            "A displayed value may be unavailable on some Windows systems.\n"
        ).format(
            now=now, computer=os.environ.get("COMPUTERNAME", platform.node()),
            windows=windows, cpu=cpu_name, cores=cpu_count, uptime=uptime,
            memory=memory_line, python=sys.version.split()[0], path=os.path.abspath(__file__)
        )
        self._set_text(self.overview, overview)

        drive_lines = [
            "DISK STORAGE\n",
            "============================================================\n",
            "Drive       Total          Used           Free           Free %\n",
            "------------------------------------------------------------\n"
        ]
        for root, size, used, free in drives:
            free_pct = (free / size * 100.0) if size else 0
            drive_lines.append("{:<10} {:<14} {:<14} {:<14} {:>5.1f}%\n".format(
                root, human_bytes(size), human_bytes(used), human_bytes(free), free_pct))
        if not drives:
            drive_lines.append("No drive information could be read.\n")
        drive_lines.append(
            "\nGuidance: keep a reasonable amount of free space on the Windows drive.\n"
            "Do not delete unfamiliar Windows or Program Files folders to free space.\n"
        )
        self._set_text(self.drives, "".join(drive_lines))

        advice_lines = [
            "BASIC HEALTH CHECK\n",
            "============================================================\n"
        ]
        if ram_percent is None:
            advice_lines.append("- RAM usage could not be measured.\n")
        elif ram_percent >= 90:
            advice_lines.append("- HIGH RAM USE: close apps you recognize and are not using. Avoid random 'RAM booster' tools.\n")
        elif ram_percent >= 75:
            advice_lines.append("- RAM use is elevated. Check which apps are open before launching more.\n")
        else:
            advice_lines.append("- RAM use does not look unusually high at this moment.\n")

        windows_drive = None
        for item in drives:
            if item[0].upper().startswith("C:"):
                windows_drive = item
                break
        if windows_drive:
            _root, size, used, free = windows_drive
            free_pct = free / size * 100.0 if size else 0
            if free_pct < 10:
                advice_lines.append("- LOW C: DRIVE SPACE: less than 10% is free. Review personal files and backups carefully.\n")
            elif free_pct < 20:
                advice_lines.append("- C: drive space is getting low. Review large personal files when convenient.\n")
            else:
                advice_lines.append("- C: drive has more than 20% free space.\n")
        else:
            advice_lines.append("- C: drive information was not available.\n")

        advice_lines.extend([
            "\nSAFE NEXT STEPS\n",
            "1. Use the Startup Items viewer to inspect what launches with Windows.\n",
            "2. Uninstall software only through Control Panel when you know what it is.\n",
            "3. Back up important files before major maintenance.\n",
            "4. Keep antivirus protection and Windows updates appropriate for your system.\n",
            "5. Avoid registry cleaners, driver-updater bundles, and one-click optimizer claims.\n\n",
            "NOT INCLUDED IN THIS VERSION\n",
            "- No automatic file deletion or temporary-file cleanup.\n",
            "- No registry edits or startup disabling.\n",
            "- No driver downloads or system repairs.\n",
            "- No claim that a scan can detect every hardware fault or malware infection.\n"
        ])
        self._set_text(self.advice, "".join(advice_lines))

        self.report_text = overview + "\n" + "".join(drive_lines) + "\n" + "".join(advice_lines)

    def show_startup(self):
        entries = read_startup_entries()
        win = tk.Toplevel(self.root)
        win.title("Startup Items - Read Only")
        win.geometry("760x430")
        win.configure(bg=BG)
        tk.Label(win, text="STARTUP ITEMS (READ-ONLY)", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=12)
        tk.Label(win, text="These entries may launch when Windows starts. This tool will not disable or remove them.",
                 bg=BG, fg=MUTED, wraplength=710, justify="left").pack(anchor="w", padx=14)
        box = tk.Text(win, bg="#0b121a", fg=TEXT, relief="flat",
                      font=("Consolas", 9), wrap="word", padx=10, pady=10)
        box.pack(fill="both", expand=True, padx=14, pady=14)
        if entries:
            for scope, name, value in entries:
                box.insert("end", "[{}] {}\n{}\n\n".format(scope, name, value))
        else:
            box.insert("end", "No Run-key entries found, or registry access is unavailable.\n")
        box.configure(state="disabled")

    def export_report(self):
        if not self.report_text:
            self.refresh()
        default_name = "Old_PC_Doctor_Report_{}.txt".format(
            datetime.now().strftime("%Y%m%d_%H%M%S"))
        path = filedialog.asksaveasfilename(
            title="Save system report", defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text report", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.report_text)
            messagebox.showinfo("Report saved", "System report saved to:\n{}".format(path))
        except Exception as exc:
            messagebox.showerror("Could not save report", str(exc))


def main():
    root = tk.Tk()
    OldPCDoctor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
