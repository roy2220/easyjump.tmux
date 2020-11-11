# easyjump.tmux

EasyMotion for Tmux

## Requirements

- Python >= 3.7
- Bash >= 5.0
- GNU Coreutils

## Installation

- [TPM](https://github.com/tmux-plugins/tpm)

  1. Add to `~/.tmux.conf`:

     ```tmux
     set-option -g @plugin "roy2220/easyjump.tmux"
     ```

  2. Press `prefix` + <kbd>I</kbd> to install the plugin.

- Manual

  1. Fetch the source:

     ```sh
     git clone https://github.com/roy2220/easyjump.tmux.git /PATH/TO/DIR
     ```

  2. Add to `~/.tmux.conf`:

     ```tmux
     run-shell "/PATH/TO/DIR/easyjump.tmux"
     ```

  3. Reload Tmux configuration:

     ```sh
     tmux source ~/.tmux.conf
     ```

## Usage

Press `prefix` + <kbd>j</kbd>

## Configuration

```tmux
# defaults:
set-option -g @easyjump-key-binding "j"
set-option -g @easyjump-label-chars "fjdkslaghrueiwoqptyvncmxzb1234567890"
set-option -g @easyjump-label-attrs "\e[1m\e[38;5;172m"
set-option -g @easyjump-text-attrs "\e[0m\e[38;5;237m"
set-option -g @easyjump-smart-case "on"
```

## Demo

https://asciinema.org/a/372086

**This project is heavily inspired by [tmux-jump](https://github.com/schasse/tmux-jump)**
