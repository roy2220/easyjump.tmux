#!/usr/bin/env python3
import datetime
import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile


def main():
    check_requirements()
    key_binding = get_option("@easyjump-key-binding") or "j"
    smart_case = get_option("@easyjump-smart-case")
    label_chars = get_option("@easyjump-label-chars")
    label_attrs = get_option("@easyjump-label-attrs")
    text_attrs = get_option("@easyjump-text-attrs")
    dir_name = os.path.dirname(os.path.abspath(__file__))
    script_file_name = os.path.join(dir_name, "easyjump.py")
    time_str = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    log_file_name = os.path.join(
        tempfile.gettempdir(), "easyjump_{}.log".format(time_str)
    )
    args = [
        "tmux",
        "bind-key",
        key_binding,
        "run-shell",
        "-b",
        shlex.join(
            [
                sys.executable,
                script_file_name,
                "--mode", "xcopy",
                "--smart-case", smart_case,
                "--label-chars", label_chars,
                "--label-attrs", label_attrs,
                "--text-attrs", text_attrs,
            ]
        )
        + " >>{} 2>&1 || true".format(shlex.quote(log_file_name)),
    ]
    subprocess.run(
        args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    args2 = args[:]
    args2[2:3] = ['-T', 'copy-mode', 'C-' + key_binding]
    subprocess.run(
        args2, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    args3 = args[:]
    args3[2:3] = ['-T', 'copy-mode-vi', 'C-' + key_binding]
    subprocess.run(
        args3, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def check_requirements():
    python_version = platform.python_version_tuple()
    if (int(python_version[0]), int(python_version[1])) < (3,8):
        raise Exception("python version >= 3.8 required")
    proc = subprocess.run(("tmux", "-V"), check=True, capture_output=True)
    result = proc.stdout.decode()[:-1]
    tmux_version = float(re.compile(r"^tmux (\d+\.\d+)").match(result).group(1))
    if tmux_version < 3.1:
        raise Exception("tmux version >= 3.1 required")


def get_option(option_name: str) -> str:
    args = ["tmux", "show-option", "-gqv", option_name]
    proc = subprocess.run(args, check=True, capture_output=True)
    option_value = proc.stdout.decode()[:-1]
    return option_value


main()
