import argparse
import itertools
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


def parse_args() -> None:
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
    arg_parser.add_argument("--auto-begin-selection")

    class Args(argparse.Namespace):
        def __init__(self) -> None:
            self.mode = ""
            self.smart_case = ""
            self.label_chars = ""
            self.label_attrs = ""
            self.text_attrs = ""
            self.print_command_only = ""
            self.key = ""
            self.cursor_pos = ""
            self.regions = ""
            self.auto_begin_selection = ""

    args = arg_parser.parse_args(sys.argv[1:], namespace=Args())

    global MODE, SMART_CASE, LABEL_CHARS, LABEL_ATTRS, TEXT_ATTRS, TEXT_ATTRS, PRINT_COMMAND_ONLY, KEY, CURSOR_POS, REGIONS, AUTO_BEGIN_SELECTION
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
    AUTO_BEGIN_SELECTION = (args.auto_begin_selection.lower() or "on") == "on"


parse_args()


class _Selection:
    x1: int
    y1: int
    x2: int
    y2: int
    is_rectangle: bool

    def __init__(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        is_rectangle: bool,
    ) -> None:
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.is_rectangle = is_rectangle


class _CopyMode:
    scroll_position: int
    cursor_x: int
    cursor_y: int
    selection: typing.Optional[_Selection]

    def __init__(
        self,
        scroll_position: int,
        cursor_x: int,
        cursor_y: int,
        selection: typing.Optional[_Selection],
    ) -> None:
        self.scroll_position = scroll_position
        self.cursor_x = cursor_x
        self.cursor_y = cursor_y
        self.selection = selection


class Screen:
    _id: str
    _tty: str
    _width: int
    _height: int
    _cursor_pos: typing.List[typing.Tuple[int, int]]
    _history_size: int
    _in_copy_mode: bool
    _copy_mode: typing.Optional[_CopyMode]
    _alternate_on: bool
    _alternate_allowed: bool
    _lines: typing.List["Line"]
    _snapshot: str

    def __init__(self) -> None:
        self._fill_info()
        if MODE == Mode.MOUSE:
            self._exit_copy_mode()
        self._lines = self._get_lines()
        if not self._alternate_allowed:
            self._snapshot = self._get_snapshot()

    def _fill_info(self) -> None:
        tmux_vars = _get_tmux_vars(
            "pane_id",
            "pane_tty",
            "pane_width",
            "pane_height",
            "cursor_x",
            "cursor_y",
            "history_size",
            "scroll_position",
            "selection_present",
            "copy_cursor_x",
            "copy_cursor_y",
            "selection_start_x",
            "selection_start_y",
            "selection_end_x",
            "selection_end_y",
            "alternate_on",
            "rectangle_toggle",
        )
        self._id = tmux_vars["pane_id"]
        self._tty = tmux_vars["pane_tty"]
        self._width = int(tmux_vars["pane_width"])
        self._height = int(tmux_vars["pane_height"])
        cursor_x = int(tmux_vars["cursor_x"])
        cursor_y = int(tmux_vars["cursor_y"])
        self._cursor_pos = [(cursor_x, cursor_y)]
        self._history_size = int(tmux_vars["history_size"])
        self._in_copy_mode = tmux_vars["scroll_position"] != ""
        if self._in_copy_mode:
            scroll_position = int(tmux_vars["scroll_position"])
            copy_cursor_x = int(tmux_vars["copy_cursor_x"])
            copy_cursor_y = int(tmux_vars["copy_cursor_y"])
            selection_present = tmux_vars["selection_present"] == "1"
            if selection_present:
                selection_start_x = int(tmux_vars["selection_start_x"])
                selection_start_y = int(tmux_vars["selection_start_y"])
                selection_start_y -= self._history_size - scroll_position  # tmux bug?
                selection_end_x = int(tmux_vars["selection_end_x"])
                selection_end_y = int(tmux_vars["selection_end_y"])
                selection_end_y -= self._history_size - scroll_position  # tmux bug?
                if (selection_start_x, selection_start_y) == (
                    copy_cursor_x,
                    copy_cursor_y,
                ):  # tmux bug?
                    selection_start_x, selection_start_y = (
                        selection_end_x,
                        selection_end_y,
                    )
                is_rectangle = tmux_vars["rectangle_toggle"] == "1"
                selection = _Selection(
                    selection_start_x,
                    selection_start_y,
                    selection_end_x,
                    selection_end_y,
                    is_rectangle,
                )
            else:
                selection = None
            self._copy_mode = _CopyMode(
                scroll_position, copy_cursor_x, copy_cursor_y, selection
            )
            self._cursor_pos.append((copy_cursor_x, copy_cursor_y))
        else:
            self._copy_mode = None
        self._alternate_on = tmux_vars["alternate_on"] == "1"
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
    ) -> typing.Generator[None, None, None]:
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
    ) -> str:
        temp: typing.List[str] = []
        for line in self._lines:
            temp.append(line.chars)
            temp.append(line.trailing_whitespaces)
        raw = "".join(temp)
        offset = 0
        segments: typing.List[str] = []
        for i, position in enumerate(positions):
            label = labels[i]
            if label == "":
                continue
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

    def _enter_alternate(self) -> None:
        with open(self._tty, "w") as f:
            f.write("\033[?1049h")
        self._alternate_on = True

    def _update(self, raw: str) -> None:
        with open(self._tty, "w") as f:
            f.write("\033[2J\033[H\033[0m")
            f.write(raw)
            cursor_x, cursor_y = self._cursor_pos[-1]
            f.write("\033[{};{}H".format(cursor_y + 1, cursor_x + 1))
        if self._copy_mode is not None and not self._alternate_on:
            self._copy_mode.scroll_position += self._height  # raw.count("\n") + 1

    def _leave_alternate(self) -> None:
        with open(self._tty, "w") as f:
            f.write("\033[?1049l")
        self._alternate_on = False

    def jump_to_pos(self, x: int, y: int) -> None:
        if MODE == MODE.XCOPY:
            ok = self._enter_copy_mode(False)
            if not ok:
                return
            if self._copy_mode is not None and self._copy_mode.selection is not None:
                selection_start_x, selection_start_y = (
                    self._copy_mode.selection.x1,
                    self._copy_mode.selection.y1,
                )
                if (y, x) > (selection_start_y, selection_start_x):
                    x += 1
            tmux_command = []
            self._xcopy_jump_to_pos(x, y, tmux_command)
            if (
                self._copy_mode is None or self._copy_mode.selection is None
            ) and AUTO_BEGIN_SELECTION:
                tmux_command += (
                    "send-keys",
                    "-t",
                    self._id,
                    "-X",
                    "begin-selection",
                    ";",
                )
            _run_tmux_command(*tmux_command)
        elif MODE == MODE.MOUSE:
            self._mouse_jump_to_pos(x, y)
        else:
            assert False

    def _xcopy_jump_to_pos(
        self, x: int, y: int, tmux_command: typing.List[str]
    ) -> None:
        cursor_x, cursor_y = self._cursor_pos[-1]
        if (x, y) == (cursor_x, cursor_y):
            return
        dy = y - cursor_y
        if dy != 0:
            tmux_command += (
                "send-keys",
                "-t",
                self._id,
                "-X",
                "-N",
                str(dy if dy > 0 else -dy),
                "cursor-down" if dy > 0 else "cursor-up",
                ";",
            )
        tmux_command += ("send-keys", "-t", self._id, "-X", "start-of-line", ";")
        char_index = _calculate_char_index(self._lines[y].chars, x)
        if char_index >= 1:
            tmux_command += (
                "send-keys",
                "-t",
                self._id,
                "-X",
                "-N",
                str(char_index),
                "cursor-right",
                ";",
            )
        self._cursor_pos[-1] = (x, y)

    def _mouse_jump_to_pos(self, x: int, y: int) -> None:
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
        return self._cursor_pos[-1]

    @property
    def lines(self) -> typing.List["Line"]:
        return self._lines

    def _exit_copy_mode(self) -> None:
        if not self._in_copy_mode:
            return
        _run_tmux_command("send-keys", "-t", self._id, "-X", "cancel")
        self._cursor_pos.pop()
        self._in_copy_mode = False

    def _enter_copy_mode(self, restore_copy_cursor: bool) -> bool:
        if self._in_copy_mode:
            return True
        _run_tmux_command("copy-mode", "-t", self._id)
        self._cursor_pos.append(self._cursor_pos[-1])
        if self._copy_mode is not None:
            history_size = self._get_history_size()
            if history_size % 2 != self._history_size % 2:
                # adapt to bug of tmux
                self._copy_mode.scroll_position -= 1
            self._history_size = history_size
            if self._copy_mode.scroll_position > self._history_size:
                return False
            tmux_command = [
                "send-keys",
                "-t",
                self._id,
                "-X",
                "goto-line",
                str(self._copy_mode.scroll_position),
                ";",
            ]
            selection = self._copy_mode.selection
            if selection is not None:
                self._xcopy_jump_to_pos(selection.x1, selection.y1, tmux_command)
                tmux_command += ("send-keys", "-t", self._id, "-X")
                if selection.is_rectangle:
                    tmux_command += (
                        "begin-selection",
                        ";",
                        "send-keys",
                        "-t",
                        self._id,
                        "-X",
                        "rectangle-on",
                        ";",
                    )
                else:
                    if self._selection_is_linewise(selection):
                        tmux_command += ("select-line", ";")
                    else:
                        tmux_command += ("begin-selection", ";")
            if restore_copy_cursor:
                self._xcopy_jump_to_pos(
                    self._copy_mode.cursor_x, self._copy_mode.cursor_y, tmux_command
                )
            _run_tmux_command(*tmux_command)
        self._in_copy_mode = True
        return True

    def _get_history_size(self) -> int:
        history_size = int(
            _run_tmux_command(
                "display-message", "-t", self._id, "-p", "#{history_size}"
            )
        )
        return history_size

    def _selection_is_linewise(
        self,
        selection: _Selection,
    ) -> bool:
        if selection.x1 != 0:
            return False
        line = self._lines[selection.y2].chars
        return _calculate_char_index(line, selection.x2) == len(line)


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
    key_length = 2
    if len(KEY) == key_length:
        return KEY
    message_template = (
        "search for key ({key_length} chars): {{:_<{key_length}}}".format(
            key_length=key_length
        )
    )
    chars = ""
    for _ in range(key_length):
        message = message_template.format(chars)
        chars += _get_char(message)
    return chars


def select_label(labels: typing.List[str]) -> int:
    min_label_length = len(labels[0])
    max_label_length = len(labels[-1])
    message_template = "goto label ("
    if min_label_length == max_label_length:
        if min_label_length == 1:
            message_template += "1 char"
        else:
            message_template += "{} chars".format(min_label_length)
    else:
        message_template += "{}~{} chars".format(min_label_length, max_label_length)
    message_template += "): {:_<" + str(max_label_length) + "}"
    label_2_label_index = {label: i for i, label in enumerate(labels)}
    chars = ""
    while True:
        message = message_template.format(chars)
        chars += _get_char(message)
        label_index = label_2_label_index.get(chars)
        if label_index is not None:
            return label_index
        if len(chars) == max_label_length:
            return -1
        for label in labels:
            if label.startswith(chars):
                break
        else:
            return -1


def _get_char(message: str) -> str:
    temp_dir_name = tempfile.mkdtemp()
    try:
        temp_file_name = os.path.join(temp_dir_name, "fifo")
        try:
            return _do_get_char(message, temp_file_name)
        finally:
            os.unlink(temp_file_name)
    finally:
        os.rmdir(temp_dir_name)


def _do_get_char(message: str, temp_file_name: str) -> str:
    os.mkfifo(temp_file_name)
    _run_tmux_command(
        "command-prompt",
        "-1",
        "-p",
        message,
        'run-shell -b "tee >> {} << EOF\\n%%%\\nEOF"'.format(
            shlex.quote(temp_file_name)
        ),
    )

    def handler(signum, frame) -> None:
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
    return len(line)


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


def generate_labels(key_length: int, number_of_positions: int) -> typing.List[str]:
    n = len(LABEL_CHARS)
    x = 1
    y = None
    while True:
        if x == key_length:
            y = 0
            break
        m = n ** x
        for i in range(m):
            if m - i + i * n >= number_of_positions:
                y = i
                break
        else:
            x += 1
            continue
        break
    labels = ["".join(p) for p in list(itertools.permutations(tuple(LABEL_CHARS), x))]
    for i in range(y):
        label_prefix = labels[i]
        for c in LABEL_CHARS:
            labels.append(label_prefix + c)
    labels = labels[y:]
    if len(labels) > number_of_positions:
        labels = labels[:number_of_positions]
    return labels


def assign_labels(
    labels: typing.List[str],
    positions: typing.List[Position],
    cursor_pos: typing.Tuple[int, int],
) -> typing.List[str]:
    if len(CURSOR_POS) == 2:
        cursor_pos = (CURSOR_POS[0] - 1, CURSOR_POS[1] - 1)

    def distance_to_cursor(position: Position) -> float:
        a = position.column_number - (cursor_pos[0] + 1)
        b = 2 * (position.line_number - (cursor_pos[1] + 1))
        c = (a * a + b * b) ** 0.5
        return c

    rank_2_position_idx = list(range(len(positions)))
    rank_2_position_idx.sort(key=lambda i: distance_to_cursor(positions[i]))
    assigned_labels = [""] * len(positions)
    for rank, position_idx in enumerate(rank_2_position_idx):
        if rank < len(labels):
            assigned_labels[position_idx] = labels[rank]
        else:
            assigned_labels[position_idx] = ""
    return assigned_labels


def find_label(
    label: str, labels: typing.List[str], positions: typing.List[Position]
) -> typing.Optional[Position]:
    for i, label2 in enumerate(labels):
        if label == label2:
            position = positions[i]
            return position
    return None


def _run_tmux_command(*args: str) -> str:
    proc = subprocess.run(("tmux", *args), check=True, capture_output=True)
    result = proc.stdout.decode()[:-1]
    return result


def _get_tmux_vars(*tmux_var_names: str) -> typing.Dict[str, str]:
    result = _run_tmux_command(
        "display-message", "-p", "\n".join("#{%s}" % s for s in tmux_var_names)
    )
    tmux_var_values = result.split("\n")
    tmux_vars = dict(zip(tmux_var_names, tmux_var_values))
    return tmux_vars


def main() -> None:
    screen = Screen()
    key = get_key()
    positions = search_for_key(screen.lines, key)
    if len(positions) == 0:
        return
    if len(positions) == 1:
        position = positions[0]
        screen.jump_to_pos(position.column_number - 1, position.line_number - 1)
        return
    labels = generate_labels(len(key), len(positions))
    assigned_labels = assign_labels(labels, positions, screen.cursor_pos)
    with screen.label_positions(positions, assigned_labels):
        label_index = select_label(labels)
    if label_index < 0:
        return
    label = labels[label_index]
    position = find_label(label, assigned_labels, positions)
    if position is None:
        return
    screen.jump_to_pos(position.column_number - 1, position.line_number - 1)


try:
    main()
except KeyboardInterrupt:
    pass
