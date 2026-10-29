# Windows Shutdown / Restart Scheduler

A lightweight Windows desktop application built with Python and Tkinter that lets you schedule automatic shutdowns and restarts. It uses Windows Task Scheduler to manage scheduled actions, so schedules can continue to run after the application window is closed.

## Features

- **Shutdown or restart** your Windows PC at a chosen time.
- **Flexible scheduling:**
  - Once — schedule a one-time action for a specific date and time.
  - Daily — repeat the action every day.
  - Weekly — choose one or more weekdays.
- **Advance reminders** — optionally show notifications 30 minutes and 5 minutes before the scheduled action.
- **30-second countdown** — gives you a short window to cancel a pending shutdown or restart.
- **Manage schedules** — view existing schedules and their next run time, delete selected schedules, or cancel all schedules.
- **Optional force close** — use `/f` to force-close applications. Unsaved work may be lost.
- **No third-party Python packages required** — uses Python's standard library and Windows tools.

## Requirements

- Windows
- Python 3.9 or later recommended
- Windows PowerShell
- A logged-in user session and a PC that is powered on or awake when the task is due

The app uses Tkinter, which is included with many standard Python installations on Windows. If your Python installation does not include Tkinter, install a Python distribution that includes it.

## Getting Started

1. Download or clone this repository.
2. Save the script as `shutdown_scheduler.py`.
3. Open Command Prompt or PowerShell in the project folder.
4. Run:

   ```bash
   python shutdown_scheduler.py
   ```

No `pip install` step is required.

## How to Use

1. **Choose an action:** `Shutdown` or `Restart`.
2. **Set the time:** use the 24-hour clock (`HH:MM`).
3. **Choose a repeat option:**
   - **Once:** enter the date in `DD / MM / YYYY` format.
   - **Daily:** run at the selected time every day.
   - **Weekly:** select one or more weekdays.
4. **Choose options:**
   - Enable reminders for 30 minutes and 5 minutes before the action.
   - Optionally enable force-closing applications.
5. Click **Schedule**.
6. Review your schedules in **Your schedules**.

### Managing scheduled actions

- **Cancel pending shutdown:** aborts a shutdown or restart that is currently in its countdown period.
- **Delete selected:** removes the selected schedule from Windows Task Scheduler.
- **Cancel ALL tasks:** removes all schedules created by this application and attempts to abort a pending shutdown or restart.
- **Refresh:** reloads the list of schedules.

## Important Notes

- **Save your work before the scheduled time.** The shutdown/restart countdown is 30 seconds.
- Enabling **Force close apps (`/f`)** may cause unsaved changes to be lost.
- Scheduled tasks are created in Windows Task Scheduler under names beginning with `AutoPower_`.
- The application does not need to remain open for a scheduled task to run.
- Tasks are configured to allow starting on battery power and to continue if the PC switches to battery power.
- A task may not run if the PC is off or asleep at the scheduled time. The script does not enable a wake timer.
- Reminder notifications depend on the Windows user session and notification environment.
- The script uses PowerShell to register and manage tasks. If task creation fails, the application displays an error message.

## Technology Stack

- Python
- Tkinter / ttk for the graphical interface
- Windows Task Scheduler
- PowerShell
- Windows `shutdown.exe`

## Project Structure

```text
.
└── shutdown_scheduler.py
```

## Safety

This application can shut down or restart your computer. Check the selected action, date, time, and repeat settings before scheduling. Use the force-close option only when you understand that unsaved work may be lost.

## License

No license has been specified. Add a license file if you intend to publish or distribute this project for reuse.
