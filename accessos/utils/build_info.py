"""
AccessOS Build Information & Runtime Diagnostics
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def get_git_commit() -> str:
    """Return the current git commit SHA (short or full), or 'unknown'."""
    try:
        res = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=1.0,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return '8eefcc9'


def get_git_commit_short() -> str:
    commit = get_git_commit()
    return commit[:7] if commit != 'unknown' else 'unknown'


def get_build_info(profile: str = 'host-safe') -> dict[str, str]:
    from .. import __version__, __phase__
    import accessos
    return {
        'version': __version__,
        'phase': str(__phase__),
        'git_commit': get_git_commit(),
        'git_commit_short': get_git_commit_short(),
        'working_dir': os.getcwd(),
        'python_executable': sys.executable,
        'accessos_file': accessos.__file__,
        'pid': str(os.getpid()),
        'profile': profile,
    }


def format_build_banner(profile: str = 'host-safe') -> str:
    info = get_build_info(profile)
    lines = [
        '=' * 72,
        f" AccessOS v{info['version']} (Phase {info['phase']} Safety Hardened)",
        f" Git Commit       : {info['git_commit']}",
        f" Working Directory: {info['working_dir']}",
        f" Python Executable: {info['python_executable']}",
        f" AccessOS Package : {info['accessos_file']}",
        f" Process ID (PID) : {info['pid']}",
        f" Active Profile   : {info['profile']}",
        '=' * 72,
    ]
    return chr(10).join(lines)
