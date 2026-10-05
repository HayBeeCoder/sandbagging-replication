"""Keeps the model's bash commands away from everything that is not its own folder.

Each run gets its own throwaway Linux user id. Its commands run as that user, with an empty
environment, so they cannot read the answer key, the API keys, or another run's files.

Run  python -m sandbag.lockdown  to check that the lock-down works on this machine.
"""
import itertools
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from sandbag.config import ROOT

PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_counter = itertools.count()


def new_uid() -> int:
    """A user id between 20000 and 59999 that no other run in this process is using."""
    return 20000 + (os.getpid() * 1000 + next(_counter)) % 40000


def as_user(uid: int, home: str, cmd: str) -> list[str]:
    """The full command line that runs cmd in bash as user uid, with a clean environment."""
    return ["setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", "--no-new-privs",  # become that user, for good
            "env", "-i", f"PATH={PATH}", f"HOME={home}",                                        # forget our environment (API keys!)
            "bash", "-c", cmd]


def check(private: Path = ROOT) -> None:
    """Refuse to continue unless an unprivileged user is shut out of the private folder."""
    if os.geteuid() != 0:
        raise RuntimeError("the local sandbox needs to start as root so it can switch to an unprivileged user")
    if not shutil.which("setpriv"):
        raise RuntimeError("the 'setpriv' command is missing; install it with: apt-get install -y util-linux")
    uid = new_uid()
    who = subprocess.run(as_user(uid, "/tmp", "id -u"), capture_output=True, text=True)
    if who.stdout.strip() != str(uid):
        raise RuntimeError(f"could not switch to an unprivileged user: {who.stderr.strip()}")
    peek = subprocess.run(as_user(uid, "/tmp", f"ls {shlex.quote(str(private))}"), capture_output=True, text=True)
    if peek.returncode == 0:
        raise RuntimeError(f"{private} can be read by the model's commands (answer key, API keys). "
                           f"Fix it with: chmod 700 {private}")


if __name__ == "__main__":
    check()
    print(f"OK: the model's commands run as an unprivileged user and cannot read {ROOT}")
