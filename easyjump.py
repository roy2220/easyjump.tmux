import argparse
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import typing
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum


class Mode(Enum):
    MOUSE = 1
    XCOPY = 2


def parse_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--mode")
    arg_parser.add_argument("--smart-case")
    arg_parser.add_argument("--label-chars")
    arg_parser.add_argument("--label-attrs")
    arg_parser.add_argument("--text-attrs")
    arg_parser.add_argument("--print-command-only")
    arg_parser.add_argument("--key")
    arg_parser.add_argument("--cursor-pos")
    arg_parser.add_argument("--regions")

    class Args(argparse.Namespace):
        def __init__(self):
            self.mode = ""
            self.smart_case = ""
            self.label_chars = ""
            self.label_attrs = ""
            self.text_attrs = ""
            self.print_command_only = ""
            self.key = ""
            self.cursor_pos = ""
            self.regions = ""

    args = arg_parser.parse_args(sys.argv[1:], namespace=Args())

    global MODE, SMART_CASE, LABEL_CHARS, LABEL_ATTRS, TEXT_ATTRS, TEXT_ATTRS, PRINT_COMMAND_ONLY, KEY, CURSOR_POS, REGIONS
    MODE = {
        "mouse": Mode.MOUSE,
        "xcopy": Mode.XCOPY,
    }[args.mode.lower() or "mouse"]
    SMART_CASE = (args.smart_case.lower() or "on") == "on"
    LABEL_CHARS = args.label_chars or "fjdkslaghrueiwoqptyvncmxzb1234567890"
    LABEL_ATTRS = args.label_attrs or "\033[1m\033[38;5;172m"
    TEXT_ATTRS = args.text_attrs or "\033[0m\033[38;5;237m"
    PRINT_COMMAND_ONLY = (
        args.print_command_only.lower() or "on"
    ) == "on"  # mouse mode only
    KEY = args.key
    CURSOR_POS = tuple(
        map(
            lambda x: int(x),
            [] if args.cursor_pos == "" else args.cursor_pos.split(",", 1),
        )
    )
    REGIONS = tuple(
        map(lambda x: int(x), [] if args.regions == "" else args.regions.split(","))
    )


parse_args()


class Screen:
    _id: str
    _tty: str
    _width: int
    _height: int
    _cursor_x: int
    _cursor_y: int
    _history_size: int
    _in_copy_mode: bool

    class _CopyMode:
        scroll_position: int
        copy_cursor_x: int
        copy_cursor_y: int
        selection_present: bool

        def __init__(
            self,
            scroll_position: int,
            copy_cursor_x: int,
            copy_cursor_y: int,
            selection_present: bool,
        ):
            self.scroll_position = scroll_position
            self.copy_cursor_x = copy_cursor_x
            self.copy_cursor_y = copy_cursor_y
            self.selection_present = selection_present

    _copy_mode: typing.Optional[_CopyMode]
    _alternate_on: bool
    _alternate_allowed: bool
    _lines: typing.List["Line"]
    _snapshot: str

    def __init__(self):
        self._fill_info()
        if MODE == Mode.MOUSE:
            self._exit_copy_mode()
        self._lines = self._get_lines()
        if not self._alternate_allowed:
            self._snapshot = self._get_snapshot()

    def _fill_info(self):
        results = _run_tmux_command(
            "display-message",
            "-p",
            "#{pane_id},"
            + "#{pane_tty},"
            + "#{pane_width},"
            + "#{pane_height},"
            + "#{cursor_x},"
            + "#{cursor_y},"
            + "#{history_size},"
            + "#{scroll_position},"
            + "#{selection_present},"
            + "#{copy_cursor_x},"
            + "#{copy_cursor_y},"
            + "#{selection_start_x},"
            + "#{selection_start_y},"
            + "#{alternate_on}",
        ).split(",")
        self._id = results[0]
        self._tty = results[1]
        self._width = int(results[2])
        self._height = int(results[3])
        self._cursor_x = int(results[4])
        self._cursor_y = int(results[5])
        self._history_size = int(results[6])
        self._in_copy_mode = results[7] != ""
        if self._in_copy_mode:
            scroll_position = int(results[7])
            selection_present = results[8] == "1"
            if selection_present:
                copy_cursor_x = int(results[11])
                copy_cursor_y = int(results[12])
                copy_cursor_y -= self._history_size - scroll_position  # tmux bug?
            else:
                copy_cursor_x = int(results[9])
                copy_cursor_y = int(results[10])
            self._copy_mode = Screen._CopyMode(
                scroll_position, copy_cursor_x, copy_cursor_y, selection_present
            )
        else:
            self._copy_mode = None
        self._alternate_on = results[13] == "1"
        if self._alternate_on:
            self._alternate_allowed = False
        else:
            result = _run_tmux_command("show-option", "-gv", "alternate-screen")
            self._alternate_allowed = result == "on"

    def _get_lines(self) -> typing.List["Line"]:
        args = ["capture-pane", "-t", self._id]
        if self._copy_mode is not None:
            start_line_number = -self._copy_mode.scroll_position
            end_line_number = start_line_number + self._height - 1
            args += ["-S", str(start_line_number), "-E", str(end_line_number)]
        args += ["-p"]
        chars_list = _run_tmux_command(*args).split("\n")
        lines: typing.List[Line] = []
        for i, chars in enumerate(chars_list):
            display_width = _calculate_display_width(chars)
            if i == len(chars_list) - 1:
                trailing_whitespaces = " " * (self._width - display_width)
            else:
                trailing_whitespaces = " " * (self._width - display_width) + "\r\n"
            line = Line(chars, trailing_whitespaces)
            lines.append(line)
        return lines

    def _get_snapshot(self) -> str:
        snapshot = _run_tmux_command(
            "capture-pane", "-t", self._id, "-e", "-p"
        ).replace("\n", "\r\n")
        return snapshot

    @contextmanager
    def label_positions(
        self, positions: typing.List["Position"], labels: typing.List[str]
    ):
        raw_with_labels = self._do_label_positions(positions, labels)
        if MODE == Mode.XCOPY:
            self._exit_copy_mode()
        if self._alternate_allowed:
            self._enter_alternate()
        self._update(raw_with_labels)
        try:
            yield
        finally:
            if self._alternate_allowed:
                self._leave_alternate()
            else:
                self._update(self._snapshot)
            if MODE == Mode.XCOPY and self._copy_mode is not None:
                self._enter_copy_mode(True)

    def _do_label_positions(
        self, positions: typing.List["Position"], labels: typing.List[str]
    ):
        temp: typing.List[str] = []
        for line in self._lines:
            temp.append(line.chars)
            temp.append(line.trailing_whitespaces)
        raw = "".join(temp)
        offset = 0
        segments: typing.List[str] = []
        for i, label in enumerate(labels):
            position = positions[i]
            if offset < position.offset:
                segment = TEXT_ATTRS + raw[offset : position.offset]
                segments.append(segment)
            segment = LABEL_ATTRS + label
            segments.append(segment)
            offset = position.offset + len(label)
        if offset < len(raw):
            segment = TEXT_ATTRS + raw[offset:]
            segments.append(segment)
        raw_with_labels = "".join(segments)
        return raw_with_labels

    def _enter_alternate(self):
        with open(self._tty, "a") as f:
            f.write("\033[?1049h")
        self._alternate_on = True

    def _update(self, raw: str):
        with open(self._tty, "a") as f:
            f.write("\033[2J\033[H\033[0m")
            f.write(raw)
            f.write("\033[{};{}H".format(self._cursor_y + 1, self._cursor_x + 1))
        if self._copy_mode is not None and not self._alternate_on:
            self._copy_mode.scroll_position += self._height  # raw.count("\n") + 1

    def _leave_alternate(self):
        with open(self._tty, "a") as f:
            f.write("\033[?1049l")
        self._alternate_on = False

    def jump_to_pos(self, x: int, y: int):
        if MODE == MODE.XCOPY:
            ok = self._enter_copy_mode(False)
            if not ok:
                return
            if (
                self._copy_mode is not None
                and self._copy_mode.selection_present
                and (y, x)
                > (self._copy_mode.copy_cursor_y, self._copy_mode.copy_cursor_x)
            ):
                x += 1
            self._xcopy_jump_to_pos(x, y)
        elif MODE == MODE.MOUSE:
            self._mouse_jump_to_pos(x, y)
        else:
            assert False

    def _xcopy_jump_to_pos(self, x: int, y: int):
        _run_tmux_command("send-keys", "-t", self._id, "-X", "top-line")
        if y >= 1:
            _run_tmux_command(
                "send-keys",
                "-t",
                self._id,
                "-X",
                "-N",
                str(y),
                "cursor-down",
            )
        char_index = _calculate_char_index(self._lines[y].chars, x)
        if self.lines[0].chars == "":
            # adapt to bug of tmux: cursor at end of line,
            line_length = len(self._lines[y].chars)
            reverse_char_index = line_length - char_index
            _run_tmux_command(
                "send-keys",
                "-t",
                self._id,
                "-X",
                "-N",
                str(reverse_char_index),
                "cursor-left",
            )
        else:
            # cursor at start of line
            if char_index >= 1:
                _run_tmux_command(
                    "send-keys",
                    "-t",
                    self._id,
                    "-X",
                    "-N",
                    str(char_index),
                    "cursor-right",
                )

    def _mouse_jump_to_pos(self, x: int, y: int):
        keys = "\033[0;{c};{l}M\033[3;{c};{l}M".format(c=x + 1, l=y + 1).encode()
        keys_in_hex = keys.hex()
        args = [
            "send-keys",
            "-t",
            self._id,
            "-H",
        ]
        args.extend(keys_in_hex[i : i + 2] for i in range(0, len(keys_in_hex), 2))
        if PRINT_COMMAND_ONLY:
            sys.stdout.write(shlex.join(("tmux", *args)))
        else:
            _run_tmux_command(*args)

    @property
    def cursor_pos(self) -> typing.Tuple[int, int]:
        if len(CURSOR_POS) == 2:
            return CURSOR_POS[0], CURSOR_POS[1]
        if self._copy_mode is not None:
            return self._copy_mode.copy_cursor_x, self._copy_mode.copy_cursor_y
        return self._cursor_x, self._cursor_y

    @property
    def lines(self) -> typing.List["Line"]:
        return self._lines

    def _exit_copy_mode(self):
        if not self._in_copy_mode:
            return
        _run_tmux_command("send-keys", "-t", self._id, "-X", "cancel")
        self._in_copy_mode = False

    def _enter_copy_mode(self, restore_copy_cursor: bool) -> bool:
        if self._in_copy_mode:
            return True
        _run_tmux_command("copy-mode", "-t", self._id)
        if self._copy_mode is not None:
            history_size = self._get_history_size()
            if history_size % 2 != self._history_size % 2:
                # adapt to bug of tmux
                self._copy_mode.scroll_position -= 1
            self._history_size = history_size
            if self._copy_mode.scroll_position > self._history_size:
                return False
            _run_tmux_command(
                "send-keys",
                "-t",
                self._id,
                "-X",
                "goto-line",
                str(self._copy_mode.scroll_position),
            )
            if (restore_copy_cursor or self._copy_mode.selection_present) and (
                self._copy_mode.copy_cursor_x,
                self._copy_mode.copy_cursor_y,
            ) != (
                self._cursor_x,
                self._cursor_y,
            ):
                self._xcopy_jump_to_pos(
                    self._copy_mode.copy_cursor_x, self._copy_mode.copy_cursor_y
                )
            if self._copy_mode.selection_present:
                _run_tmux_command(
                    "send-keys",
                    "-t",
                    self._id,
                    "-X",
                    "begin-selection",
                )
        self._in_copy_mode = True
        return True

    def _get_history_size(self) -> int:
        history_size = int(
            _run_tmux_command(
                "display-message", "-t", self._id, "-p", "#{history_size}"
            )
        )
        return history_size


@dataclass
class Line:
    chars: str
    trailing_whitespaces: str


@dataclass
class Position:
    line_number: int
    column_number: int
    offset: int


def get_key() -> str:
    if len(KEY) == 2:
        return KEY
    return _get_chars("search for key", 2, None)


def get_label(label_length, candidate_labels: typing.List[str]) -> typing.Optional[str]:
    try:
        return _get_chars("goto label", label_length, candidate_labels)
    except ValueError:
        return None


def _get_chars(
    prompt: str,
    number_of_chars: int,
    expected_chars_list: typing.Optional[typing.List[str]],
) -> str:
    format = "{} ({} char"
    if number_of_chars >= 2:
        format += "s"
    format += "): {:_<" + str(number_of_chars) + "}"
    chars = ""
    for _ in range(number_of_chars):
        prompt_with_input = format.format(prompt, number_of_chars, chars)
        chars += _get_char(prompt_with_input)
        if expected_chars_list is not None:
            for expected_chars in expected_chars_list:
                if expected_chars.startswith(chars):
                    break
            else:
                raise ValueError()
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
    _run_tmux_command(
        "command-prompt",
        "-1",
        "-p",
        prompt,
        'run-shell -b "tee >> {} << EOF\\n%%%\\nEOF"'.format(
            shlex.quote(temp_file_name)
        ),
    )

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
    if char == "":
        raise SystemExit()
    return char


def search_for_key(lines: typing.List[Line], key: str) -> typing.List[Position]:
    lower_key = key.lower()
    line_offset = 0
    positions: typing.List[Position] = []
    for line_index, line in enumerate(lines):
        lower_line_chars = line.chars.lower()
        char_index = -len(key)
        while True:
            char_index = lower_line_chars.find(lower_key, char_index + len(key))
            if char_index < 0:
                break
            potential_key = line.chars[char_index : char_index + len(key)]
            if not _test_potential_key(potential_key, key):
                continue
            column_index = _calculate_display_width(line.chars[:char_index])
            if not _point_is_in_region(column_index + 1, line_index + 1):
                continue
            offset = line_offset + char_index
            position = Position(line_index + 1, column_index + 1, offset)
            positions.append(position)
        line_offset += len(line.chars) + len(line.trailing_whitespaces)
    return positions


def _calculate_char_index(line: str, x: int) -> int:
    display_width = 0
    for i, c in enumerate(line):
        if display_width >= x:
            return i
        if unicodedata.east_asian_width(c) == "W":
            display_width += 2
        else:
            display_width += 1
    return 0


def _calculate_display_width(s: str) -> int:
    display_width = 0
    for c in s:
        if unicodedata.east_asian_width(c) == "W":
            display_width += 2
        else:
            display_width += 1
    return display_width


def _test_potential_key(potential_key: str, key: str) -> bool:
    if potential_key == key:
        return True
    if not SMART_CASE:
        return False
    for c in key:
        if c.isupper():
            return False
    return True


def _point_is_in_region(x: int, y: int) -> bool:
    n = len(REGIONS)
    if n == 0:
        return True
    for i in range(0, n, 4):
        region = REGIONS[i : i + 4]
        if x >= region[0] and y >= region[1] and x <= region[2] and y <= region[3]:
            return True
    return False


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
    cursor_pos: typing.Tuple[int, int],
):
    def distance_to_cursor(position: Position) -> float:
        a = position.column_number - (cursor_pos[0] + 1)
        b = 2 * (position.line_number - (cursor_pos[1] + 1))
        c = (a * a + b * b) ** 0.5
        return c

    rank_2_position_idx = list(range(len(labels)))
    rank_2_position_idx.sort(key=lambda i: distance_to_cursor(positions[i]))
    sorted_labels = [""] * len(labels)
    for rank, position_idx in enumerate(rank_2_position_idx):
        sorted_labels[position_idx] = labels[rank]
    labels[:] = sorted_labels


def find_label(
    label: str, labels: typing.List[str], positions: typing.List[Position]
) -> typing.Optional[Position]:
    for i, label2 in enumerate(labels):
        if label == label2:
            position = positions[i]
            return position
    return None


def _run_tmux_command(*args: str):
    proc = subprocess.run(("tmux", *args), check=True, capture_output=True)
    result = proc.stdout.decode()[:-1]
    return result


def main():
    screen = Screen()
    key = get_key()
    positions = search_for_key(screen.lines, key)
    if len(positions) == 0:
        return
    if len(positions) == 1:
        position = positions[0]
        screen.jump_to_pos(position.column_number - 1, position.line_number - 1)
        return
    labels, label_length = generate_labels(len(key), len(positions))
    sort_labels(labels, positions, screen.cursor_pos)
    with screen.label_positions(positions, labels):
        label = get_label(label_length, labels)
    if label is None:
        return
    position = find_label(label, labels, positions)
    if position is None:
        return
    screen.jump_to_pos(position.column_number - 1, position.line_number - 1)


try:
    main()
except KeyboardInterrupt:
    pass
