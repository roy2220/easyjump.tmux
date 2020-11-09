import os
import shlex
import signal
import subprocess
import sys
import tempfile
import typing
import unicodedata
from dataclasses import dataclass

LABEL_CHARS = sys.argv[1]
LABEL_ATTRS = sys.argv[2]
TEXT_ATTRS = sys.argv[3]
SMART_CASE = sys.argv[4] == "on"


@dataclass
class Line:
    chars: str
    trailing_whitespaces: str


class Screen:
    _id: str
    _tty: str
    _width: int
    _cursor_x: int
    _cursor_y: int
    _lines: typing.List[Line]
    _snapshot: str

    def __init__(self):
        self._fill_info()
        self._lines = self._get_lines()
        self._snapshot = self._get_snapshot()

    def update(self, raw: str):
        with open(self._tty, "a") as f:
            f.write("\033[2J\033[H")
            f.write(raw)
            f.write("\033[{};{}H".format(self._cursor_y + 1, self._cursor_x + 1))

    def jump_to_location(self, line_number: int, column_number: int):
        args = ["tmux", "copy-mode", "-t", self._id]
        subprocess.run(args, check=True)
        args = ["tmux", "send-keys", "-t", self._id, "-X", "top-line"]
        subprocess.run(args, check=True)
        if line_number >= 2:
            args = [
                "tmux",
                "send-keys",
                "-t",
                self._id,
                "-X",
                "-N",
                str(line_number - 1),
                "cursor-down",
            ]
            subprocess.run(args, check=True)
        args = ["tmux", "send-keys", "-X", "start-of-line", "-t", self._id]
        subprocess.run(args, check=True)
        if column_number >= 2:
            args = [
                "tmux",
                "send-keys",
                "-t",
                self._id,
                "-X",
                "-N",
                str(column_number - 1),
                "cursor-right",
            ]
            subprocess.run(args, check=True)

    def restore(self):
        self.update(self._snapshot)

    @property
    def width(self) -> int:
        return self._width

    @property
    def cursor_x(self) -> int:
        return self._cursor_x

    @property
    def cursor_y(self) -> int:
        return self._cursor_y

    @property
    def lines(self) -> typing.List[Line]:
        return self._lines

    def _fill_info(self):
        Screen._exit_mode()
        args = [
            "tmux",
            "display-message",
            "-p",
            "#{pane_id},#{pane_tty},#{pane_width},#{cursor_x},#{cursor_y}",
        ]
        proc = subprocess.run(args, check=True, capture_output=True)
        results = proc.stdout.decode().split(",")
        self._id = results[0]
        self._tty = results[1]
        self._width = int(results[2])
        self._cursor_x = int(results[3])
        self._cursor_y = int(results[4])

    def _get_snapshot(self) -> str:
        args = ["tmux", "capture-pane", "-t", self._id, "-e", "-p"]
        proc = subprocess.run(args, check=True, capture_output=True)
        snapshot = proc.stdout.decode()[:-1].replace("\n", "\r\n")
        return snapshot

    def _get_lines(self) -> typing.List[Line]:
        args = ["tmux", "capture-pane", "-t", self._id, "-p"]
        proc = subprocess.run(args, check=True, capture_output=True)
        chars_list = proc.stdout.decode()[:-1].split("\n")
        lines: typing.List[Line] = []
        for i, chars in enumerate(chars_list):
            display_width = sum(
                map(
                    lambda c: 2 if unicodedata.east_asian_width(c) == "W" else 1,
                    chars,
                )
            )
            if i == len(chars_list) - 1:
                trailing_whitespaces = " " * (self._width - display_width)
            else:
                trailing_whitespaces = " " * (self._width - display_width) + "\r\n"
            line = Line(
                chars,
                trailing_whitespaces,
            )
            lines.append(line)
        return lines

    @staticmethod
    def _exit_mode():
        args = ["tmux", "send-keys", "-X", "cancel"]
        subprocess.run(args)


def get_key() -> str:
    return _get_chars("search key", 2)


def get_label(label_length) -> str:
    return _get_chars("goto label", label_length)


def _get_chars(prompt: str, number_of_chars: int) -> str:
    format = "{} ({} char"
    if number_of_chars >= 2:
        format += "s"
    format += "): {:_<" + str(number_of_chars) + "}"
    chars = ""
    for _ in range(number_of_chars):
        prompt_with_input = format.format(prompt, number_of_chars, chars)
        chars += _get_char(prompt_with_input)
    return chars


def _get_char(prompt: str) -> str:
    temp_dir_name = tempfile.mkdtemp()
    try:
        temp_file_name = os.path.join(temp_dir_name, "fifo")
        try:
            return _do_get_char(prompt, temp_file_name)
        finally:
            os.unlink(temp_file_name)
    finally:
        os.rmdir(temp_dir_name)


def _do_get_char(prompt: str, temp_file_name: str) -> str:
    os.mkfifo(temp_file_name)
    args = [
        "tmux",
        "command-prompt",
        "-1",
        "-p",
        prompt,
        'run-shell -b "tee >> {} << EOF\\n%1\\nEOF"'.format(
            shlex.quote(temp_file_name)
        ),
    ]
    subprocess.run(args, check=True)

    def handler(signum, frame):
        raise TimeoutError()

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(30)

    try:
        with open(temp_file_name, "r") as f:
            char = f.readline()[:-1]
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
    return char


@dataclass
class Position:
    line_number: int
    column_number: int
    offset: int


def search_key(lines: typing.List[Line], key: str) -> typing.List[Position]:
    lower_key = key.lower()
    line_offset = 0
    positions: typing.List[Position] = []
    for line_index, line in enumerate(lines):
        lower_line_chars = line.chars.lower()
        column_index = -len(key)
        while True:
            column_index = lower_line_chars.find(lower_key, column_index + len(key))
            if column_index < 0:
                break
            potential_key = line.chars[column_index : column_index + len(key)]
            if not _test_potential_key(potential_key, key):
                continue
            offset = line_offset + column_index
            position = Position(line_index + 1, column_index + 1, offset)
            positions.append(position)
        line_offset += len(line.chars) + len(line.trailing_whitespaces)
    return positions


def _test_potential_key(potential_key: str, key: str) -> bool:
    if potential_key == key:
        return True
    if not SMART_CASE:
        return False
    for c in key:
        if c.isupper():
            return False
    return True


def generate_labels(
    key_length: int, number_of_positions: int
) -> typing.Tuple[typing.List[str], int]:
    label_length = 1
    while len(LABEL_CHARS) ** label_length < number_of_positions:
        if label_length == min(key_length, len(LABEL_CHARS)):
            break
        label_length += 1
    labels: typing.List[str] = []

    def do_generate_labels(label_prefix) -> bool:
        if len(label_prefix) == label_length - 1:
            for label_char in LABEL_CHARS:
                if len(labels) == number_of_positions:
                    return True
                label = label_prefix + label_char
                labels.append(label)
        else:
            for label_char in LABEL_CHARS:
                stop = do_generate_labels(label_prefix + label_char)
                if stop:
                    return True
        return False

    do_generate_labels("")
    return labels, label_length


def sort_labels(
    labels: typing.List[str],
    positions: typing.List[Position],
    screen_width: int,
    cursor_x: int,
    cursor_y: int,
):
    cursor_offset = cursor_y * screen_width + cursor_x
    rank_2_position_idx = list(range(len(labels)))
    rank_2_position_idx.sort(key=lambda i: abs(positions[i].offset - cursor_offset))
    sorted_labels = [""] * len(labels)
    for rank, position_idx in enumerate(rank_2_position_idx):
        sorted_labels[position_idx] = labels[rank]
    labels[:] = sorted_labels


def label_keys(
    lines: typing.List[Line], positions: typing.List[Position], labels: typing.List[str]
) -> str:
    temp: typing.List[str] = []
    for line in lines:
        temp.append(line.chars)
        temp.append(line.trailing_whitespaces)
    raw_screen = "".join(temp)
    offset = 0
    segments: typing.List[str] = []
    for i, label in enumerate(labels):
        position = positions[i]
        if offset < position.offset:
            segment = TEXT_ATTRS + raw_screen[offset : position.offset]
            segments.append(segment)
        segment = LABEL_ATTRS + label
        segments.append(segment)
        offset = position.offset + len(label)
    if offset < len(raw_screen):
        segment = TEXT_ATTRS + raw_screen[offset:]
        segments.append(segment)
    raw_screen_with_labels = "".join(segments)
    return raw_screen_with_labels


def find_label(
    label: str, labels: typing.List[str], positions: typing.List[Position]
) -> typing.Optional[Position]:
    for i, label2 in enumerate(labels):
        if label == label2:
            position = positions[i]
            return position
    return None


def main():
    screen = Screen()
    key = get_key()
    positions = search_key(screen.lines, key)
    if len(positions) == 0:
        return
    labels, label_length = generate_labels(len(key), len(positions))
    sort_labels(labels, positions, screen.width, screen.cursor_x, screen.cursor_y)
    raw_screen_with_labels = label_keys(screen.lines, positions, labels)
    screen.update(raw_screen_with_labels)
    try:
        label = get_label(label_length)
        position = find_label(label, labels, positions)
    finally:
        screen.restore()
    if position is None:
        return
    screen.jump_to_location(position.line_number, position.column_number)


main()
