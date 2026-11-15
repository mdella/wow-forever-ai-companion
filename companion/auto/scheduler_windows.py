"""Windows: a Task Scheduler task runs the gatekeeper every few minutes while the player is signed
in. Task Scheduler cannot watch a file, so the gatekeeper compares the save file's timestamp; an
unchanged file is a few milliseconds of work and never starts the AI. pythonw.exe runs it without
a console window."""
import base64, os, subprocess

TASK = os.environ.get("AIC_AUTO_TASK", "AICompanionAuto")
EVERY_MINUTES = 5
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _ps(script):
    """Run a PowerShell script without quoting trouble (encoded), hidden."""
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-EncodedCommand", enc], capture_output=True, text=True, creationflags=NO_WINDOW)


def _q(s):
    """A PowerShell single-quoted string."""
    return "'" + str(s).replace("'", "''") + "'"


def pythonw(python):
    d, name = os.path.split(python)
    w = os.path.join(d, name.lower().replace("python.exe", "pythonw.exe"))
    return w if os.path.exists(w) else python


def task_script(python, script, workdir, home=None):
    args = '-I "%s" poll' % script
    # AIC_AUTO_HOME (tests only) is not inherited by a scheduled task, so hand it on explicitly.
    if home:
        args = '-c "import os,runpy,sys; os.environ[\'AIC_AUTO_HOME\']=r\'%s\'; sys.argv=[r\'%s\',\'poll\']; ' \
               'runpy.run_path(r\'%s\', run_name=\'__main__\')"' % (home, script, script)
    return """
$a = New-ScheduledTaskAction -Execute {exe} -Argument {args} -WorkingDirectory {wd}
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes {every}) -RepetitionDuration (New-TimeSpan -Days 3650)
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName {task} -Action $a -Trigger $t -Settings $s -Principal $p -Description 'AI Companion automatic updates' -Force | Out-Null
""".format(exe=_q(pythonw(python)), args=_q(args), wd=_q(workdir), every=EVERY_MINUTES, task=_q(TASK))


def install(cfg, script):
    if not cfg.saved_variables:
        return "Could not find the game's SavedVariables folder. Run check for what to fix."
    r = _ps(task_script(cfg["python"], script, os.path.dirname(script), os.environ.get("AIC_AUTO_HOME")))
    if r.returncode != 0 or not installed():
        return "Could not create the scheduled task: %s" % ((r.stderr or r.stdout).strip() or r.returncode)
    return "Checking %s every %d minutes while you're signed in." % (os.path.dirname(cfg.saved_variables), EVERY_MINUTES)


def uninstall():
    _ps("Unregister-ScheduledTask -TaskName %s -Confirm:$false -ErrorAction SilentlyContinue" % _q(TASK))
    return "Stopped watching. Settings and logs are kept."


def installed():
    r = _ps("if (Get-ScheduledTask -TaskName %s -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" % _q(TASK))
    return r.returncode == 0


def notify(title, text):
    _ps("""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip(10000, {t}, {m}, 'Info')
Start-Sleep -Seconds 10
$n.Dispose()
""".format(t=_q(title), m=_q(text)))
