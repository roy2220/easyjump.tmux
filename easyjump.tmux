#!/usr/bin/env python3
import datetime
import os
import shlex
import subprocess
import sys
import tempfile


def get_option(option_name: str, default_option_value: str) -> str:
    args = ["tmux", "show-option", "-gqv", option_name]
    proc = subprocess.run(args, check=True, capture_output=True)
    option_value = proc.stdout.decode()[:-1]
    if option_value == "":
        option_value = default_option_value
    return option_value


def main():
    key_binding = get_option("@easyjump-key-binding", "j")
    label_chars = get_option(
        "@easyjump-label-chars", "fjdkslaghrueiwoqptyvncmxzb1234567890"
    )
    label_attrs = get_option("@easyjump-label-attrs", "\033[1m\033[38;5;172m")
    text_attrs = get_option("@easyjump-text-attrs", "\033[0m\033[38;5;237m")
    smart_case = get_option("@easyjump-smart-case", r"on")
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
                label_chars,
                label_attrs,
                text_attrs,
                smart_case,
            ]
        )
        + " >>{} 2>&1 || true".format(shlex.quote(log_file_name)),
    ]
    subprocess.run(
        args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


main()
