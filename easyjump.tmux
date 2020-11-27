#!/usr/bin/env python3
import datetime
import os
import shlex
import subprocess
import sys
import tempfile


def get_option(option_name: str) -> str:
    args = ["tmux", "show-option", "-gqv", option_name]
    proc = subprocess.run(args, check=True, capture_output=True)
    option_value = proc.stdout.decode()[:-1]
    return option_value


def main():
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


main()
