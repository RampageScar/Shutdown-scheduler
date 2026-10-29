"""
Shutdown / Restart Scheduler for Windows (Python + Tkinter, no extra packages).

How it works
------------
Every schedule (one-time, daily or weekly) is stored as Windows Task Scheduler
tasks named  AutoPower_<id>_main / _n30 / _n5.
  * _main : runs `shutdown` (with a 30 second grace period you can abort)
  * _n30  : pop-up notification 30 minutes before
  * _n5   : pop-up notification 5 minutes before
Because Windows owns the tasks, they still fire after you close this window
or reboot. Tasks run as your own user, so admin rights are normally not needed.
Note: tasks only run while you are logged on and the PC is on (or awake).
"""

import base64
import json
import subprocess
import tkinter as tk
import uuid
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

PREFIX = "AutoPower"
GRACE_SECONDS = 30
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# --------------------------------------------------------------------------
# PowerShell helpers
# --------------------------------------------------------------------------
def run_ps(script):
    """Run a PowerShell script (encoded, so no quoting problems)."""
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-EncodedCommand", enc],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def notify_args(title, text):
    """Arguments for a powershell.exe call that shows a tray balloon / toast."""
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
        "$n=New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon=[System.Drawing.SystemIcons]::Warning;"
        "$n.Visible=$true;"
        f"$n.ShowBalloonTip(20000,{ps_quote(title)},{ps_quote(text)},"
        "[System.Windows.Forms.ToolTipIcon]::Warning);"
        "Start-Sleep -Seconds 21;$n.Dispose()"
    )
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    return f"-NoProfile -WindowStyle Hidden -EncodedCommand {enc}"


# --------------------------------------------------------------------------
# Building the scheduled tasks
# --------------------------------------------------------------------------
def trigger_expr(repeat, base_dt, offset, days):
    """PowerShell expression for a trigger `offset` minutes before base_dt."""
    t = base_dt - timedelta(minutes=offset)
    at = f"([datetime]'{t:%Y-%m-%dT%H:%M:%S}')"
    if repeat == "Once":
        return f"New-ScheduledTaskTrigger -Once -At {at}"
    if repeat == "Daily":
        return f"New-ScheduledTaskTrigger -Daily -At {at}"
    # Weekly: moving earlier may cross midnight, which shifts the weekday back
    shift = (t.date() - base_dt.date()).days
    shifted = [DAYS[(DAYS.index(d) + shift) % 7] for d in days]
    return f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {','.join(shifted)} -At {at}"


def build_register_script(sid, action, repeat, hh, mm, date, days, force, notify):
    now = datetime.now()
    if repeat == "Once":
        base = datetime(date.year, date.month, date.day, hh, mm)
    else:  # reference Monday, only the time of day (and weekday shift) matter
        base = datetime(2000, 1, 3, hh, mm)

    flag = "s" if action == "Shutdown" else "r"
    verb = "shutdown" if action == "Shutdown" else "restart"
    shut_args = (f'/{flag} /t {GRACE_SECONDS} /c "Scheduled {verb} in {GRACE_SECONDS} '
                 f'seconds. To cancel run: shutdown /a"')
    if force:
        shut_args += " /f"

    if repeat == "Once":
        when = f"{base:%Y-%m-%d} {hh:02d}:{mm:02d}"
    elif repeat == "Daily":
        when = f"daily {hh:02d}:{mm:02d}"
    else:
        when = f"{', '.join(d[:3] for d in days)} {hh:02d}:{mm:02d}"
    meta = {"action": action, "repeat": repeat, "when": when, "force": force, "notify": notify}
    desc = ps_quote(json.dumps(meta))

    jobs = [("main", 0, "shutdown.exe", shut_args)]
    if notify:
        for mins in (30, 5):
            text = f"Your PC will {verb} in {mins} minutes ({hh:02d}:{mm:02d}). Save your work."
            jobs.append((f"n{mins}", mins, "powershell.exe",
                         notify_args(f"Scheduled {verb}", text)))

    lines = [
        "$ErrorActionPreference='Stop'",
        "$s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries",
    ]
    for name, offset, exe, args in jobs:
        if repeat == "Once" and (base - timedelta(minutes=offset)) <= now:
            continue  # that moment is already in the past, skip this reminder
        trig = trigger_expr(repeat, base, offset, days)
        lines.append(
            f"Register-ScheduledTask -TaskName {ps_quote(f'{PREFIX}_{sid}_{name}')} "
            f"-Action (New-ScheduledTaskAction -Execute {ps_quote(exe)} -Argument {ps_quote(args)}) "
            f"-Trigger ({trig}) -Settings $s -Description {desc} -Force | Out-Null"
        )
    return "\n".join(lines)


def list_schedules():
    script = (
        f"$o=@(Get-ScheduledTask -TaskName '{PREFIX}_*_main' -ErrorAction SilentlyContinue | "
        "ForEach-Object { $i=Get-ScheduledTaskInfo -InputObject $_; "
        "[pscustomobject]@{Name=$_.TaskName;Desc=$_.Description;"
        "Next=$(if($i.NextRunTime -and $i.NextRunTime.Year -gt 2000)"
        "{$i.NextRunTime.ToString('yyyy-MM-dd HH:mm')}else{''})} });"
        "ConvertTo-Json -InputObject $o -Compress"
    )
    code, out, err = run_ps(script)
    if code != 0 or not out or out == "null":
        return []
    data = json.loads(out)
    return [data] if isinstance(data, dict) else data


def remove_schedule(sid):
    pattern = f"{PREFIX}_{sid}_*" if sid else f"{PREFIX}_*"
    return run_ps(
        f"Get-ScheduledTask -TaskName '{pattern}' -ErrorAction SilentlyContinue | "
        "Unregister-ScheduledTask -Confirm:$false"
    )


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Shutdown / Restart Scheduler")
        self.resizable(False, False)
        now = datetime.now()

        self.action = tk.StringVar(value="Shutdown")
        self.repeat = tk.StringVar(value="Once")
        self.force = tk.BooleanVar(value=False)
        self.notify = tk.BooleanVar(value=True)
        self.hour = tk.StringVar(value="23")
        self.minute = tk.StringVar(value="00")
        self.day = tk.StringVar(value=f"{now.day:02d}")
        self.month = tk.StringVar(value=f"{now.month:02d}")
        self.year = tk.StringVar(value=str(now.year))
        self.dayvars = {d: tk.BooleanVar(value=False) for d in DAYS}

        pad = {"padx": 10, "pady": 4}
        main = ttk.Frame(self, padding=8)
        main.grid()

        # Action
        f = ttk.LabelFrame(main, text="Action")
        f.grid(row=0, column=0, sticky="ew", **pad)
        ttk.Radiobutton(f, text="Shutdown", variable=self.action, value="Shutdown").grid(row=0, column=0, padx=10, pady=4)
        ttk.Radiobutton(f, text="Restart", variable=self.action, value="Restart").grid(row=0, column=1, padx=10, pady=4)

        # Time
        f = ttk.LabelFrame(main, text="Time (24-hour)")
        f.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Spinbox(f, from_=0, to=23, width=4, wrap=True, format="%02.0f", textvariable=self.hour).grid(row=0, column=0, padx=(10, 2), pady=6)
        ttk.Label(f, text=":").grid(row=0, column=1)
        ttk.Spinbox(f, from_=0, to=59, width=4, wrap=True, format="%02.0f", textvariable=self.minute).grid(row=0, column=2, padx=(2, 10), pady=6)

        # Repeat
        f = ttk.LabelFrame(main, text="Repeat")
        f.grid(row=2, column=0, sticky="ew", **pad)
        for i, r in enumerate(("Once", "Daily", "Weekly")):
            ttk.Radiobutton(f, text=r, variable=self.repeat, value=r, command=self.update_repeat).grid(row=0, column=i, padx=10, pady=4)

        self.date_frame = ttk.Frame(f)
        ttk.Label(self.date_frame, text="Date (DD / MM / YYYY):").grid(row=0, column=0, padx=(10, 4))
        ttk.Spinbox(self.date_frame, from_=1, to=31, width=3, format="%02.0f", textvariable=self.day).grid(row=0, column=1)
        ttk.Spinbox(self.date_frame, from_=1, to=12, width=3, format="%02.0f", textvariable=self.month).grid(row=0, column=2, padx=2)
        ttk.Spinbox(self.date_frame, from_=now.year, to=now.year + 5, width=6, textvariable=self.year).grid(row=0, column=3)
        self.date_frame.grid(row=1, column=0, columnspan=3, pady=6, sticky="w")

        self.days_frame = ttk.Frame(f)
        for i, d in enumerate(DAYS):
            ttk.Checkbutton(self.days_frame, text=d[:3], variable=self.dayvars[d]).grid(row=0, column=i, padx=4)

        # Options
        f = ttk.LabelFrame(main, text="Options")
        f.grid(row=3, column=0, sticky="ew", **pad)
        ttk.Checkbutton(f, text="Force close apps (/f) - unsaved work will be lost",
                        variable=self.force).grid(row=0, column=0, sticky="w", padx=10, pady=2)
        ttk.Checkbutton(f, text="Notify 30 min and 5 min before",
                        variable=self.notify).grid(row=1, column=0, sticky="w", padx=10, pady=2)
        ttk.Label(f, text=f"A {GRACE_SECONDS}-second countdown runs first; 'Cancel pending' aborts it.",
                  foreground="gray").grid(row=2, column=0, sticky="w", padx=10, pady=2)

        # Buttons
        f = ttk.Frame(main)
        f.grid(row=4, column=0, sticky="ew", **pad)
        ttk.Button(f, text="Schedule", command=self.on_schedule).grid(row=0, column=0, padx=3)
        ttk.Button(f, text="Cancel pending shutdown", command=self.on_abort).grid(row=0, column=1, padx=3)

        # Existing schedules
        f = ttk.LabelFrame(main, text="Your schedules")
        f.grid(row=5, column=0, sticky="ew", **pad)
        self.tree = ttk.Treeview(f, columns=("what", "when", "opts", "next"), show="headings", height=6)
        for col, text, w in (("what", "Action", 80), ("when", "When", 150), ("opts", "Options", 110), ("next", "Next run", 120)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor="w")
        self.tree.grid(row=0, column=0, columnspan=3, padx=6, pady=6)
        ttk.Button(f, text="Delete selected", command=self.on_delete).grid(row=1, column=0, padx=6, pady=(0, 6), sticky="w")
        ttk.Button(f, text="Cancel ALL tasks", command=self.on_cancel_all).grid(row=1, column=1, padx=6, pady=(0, 6), sticky="w")
        ttk.Button(f, text="Refresh", command=self.refresh).grid(row=1, column=2, padx=6, pady=(0, 6), sticky="e")

        self.status = ttk.Label(main, text="", foreground="gray")
        self.status.grid(row=6, column=0, sticky="w", **pad)

        self.update_repeat()
        self.after(100, self.refresh)

    # ---- helpers ----
    def busy(self, on):
        self.config(cursor="watch" if on else "")
        self.update_idletasks()

    def update_repeat(self):
        self.date_frame.grid_remove()
        self.days_frame.grid_remove()
        if self.repeat.get() == "Once":
            self.date_frame.grid(row=1, column=0, columnspan=3, pady=6, sticky="w")
        elif self.repeat.get() == "Weekly":
            self.days_frame.grid(row=1, column=0, columnspan=3, pady=6, sticky="w")

    def refresh(self):
        self.busy(True)
        try:
            items = list_schedules()
            # tidy up one-time tasks that have already run
            live = []
            for it in items:
                meta = json.loads(it["Desc"] or "{}")
                sid = it["Name"].split("_")[1]
                if meta.get("repeat") == "Once" and not it["Next"]:
                    remove_schedule(sid)
                else:
                    live.append((sid, meta, it["Next"]))
            self.tree.delete(*self.tree.get_children())
            for sid, meta, nxt in live:
                opts = ("force " if meta.get("force") else "") + ("notify" if meta.get("notify") else "")
                self.tree.insert("", "end", iid=sid, values=(meta.get("action", "?"), meta.get("when", "?"), opts.strip() or "-", nxt or "-"))
            self.status.config(text=f"{len(live)} schedule(s).")
        except Exception as e:  # noqa: BLE001
            self.status.config(text=f"Could not read schedules: {e}")
        finally:
            self.busy(False)

    # ---- button handlers ----
    def on_schedule(self):
        try:
            hh, mm = int(self.hour.get()), int(self.minute.get())
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except ValueError:
            return messagebox.showerror("Invalid time", "Please enter a valid 24-hour time.")

        repeat = self.repeat.get()
        date = None
        days = [d for d in DAYS if self.dayvars[d].get()]
        if repeat == "Once":
            try:
                date = datetime(int(self.year.get()), int(self.month.get()), int(self.day.get()))
            except ValueError:
                return messagebox.showerror("Invalid date", "That date doesn't exist.")
            if datetime(date.year, date.month, date.day, hh, mm) <= datetime.now() + timedelta(minutes=1):
                return messagebox.showerror("Too soon", "Pick a time at least a minute in the future.")
        elif repeat == "Weekly" and not days:
            return messagebox.showerror("No days", "Tick at least one weekday.")

        if self.force.get() and not messagebox.askyesno(
                "Force close apps?", "Apps will be closed without saving. Continue?"):
            return

        sid = uuid.uuid4().hex[:6]
        script = build_register_script(sid, self.action.get(), repeat, hh, mm, date,
                                       days, self.force.get(), self.notify.get())
        self.busy(True)
        code, out, err = run_ps(script)
        self.busy(False)
        if code != 0:
            return messagebox.showerror("Could not schedule", err or out or "Unknown error")
        self.status.config(text="Scheduled.")
        self.refresh()

    def on_abort(self):
        r = subprocess.run(["shutdown", "/a"], capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode == 0:
            messagebox.showinfo("Cancelled", "The pending shutdown/restart was aborted.")
        else:
            messagebox.showinfo("Nothing to cancel", "No shutdown is currently counting down.")

    def on_delete(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("Select one", "Select a schedule first.")
        self.busy(True)
        for sid in sel:
            remove_schedule(sid)
        self.busy(False)
        self.refresh()

    def on_cancel_all(self):
        if not messagebox.askyesno("Cancel all", "Delete ALL schedules and abort any pending shutdown?"):
            return
        self.busy(True)
        remove_schedule(None)
        subprocess.run(["shutdown", "/a"], capture_output=True, creationflags=NO_WINDOW)
        self.busy(False)
        self.refresh()
        self.status.config(text="All schedules cancelled.")


if __name__ == "__main__":
    App().mainloop()
