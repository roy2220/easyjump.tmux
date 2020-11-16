# easyjump.tmux

EasyMotion for Tmux

## Demonstration

📹: https://asciinema.org/a/372086

**This project is heavily inspired by [tmux-jump](https://github.com/schasse/tmux-jump)**.

There some differences between `tmux-jump` and `easyjump.tmux`:

- `easyjump.tmux` can be integrated into Vim/Neovim! 🔥 See [Integration with Vim](#integration-with-vim) for more details.
- `easyjump.tmux` supports the smart case-insensitive search (turned on by default).
- `tmux-jump` searches by 1 char and `easyjump.tmux` does by 2 chars.
- `tmux-jump` only matches the prefixes of words, `easyjump.tmux` matches all substrings.
- `tmux-jump` is implemented in Ruby and `easyjump.tmux` is done in Python 3 with type hints.

## Requirements

- Python >= 3.8

**Windows is not supported now.**

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

- Press `prefix` + <kbd>j</kbd> to invoke EasyJump.
- Press <kbd>Ctrl</kbd> + <kbd>j</kbd> to invoke EasyJump in `copy mode`.
- Press <kbd>Enter</kbd> to cancel EasyJump.

## Configuration

defaults:

```tmux
set-option -g @easyjump-key-binding "j"
set-option -g @easyjump-smart-case "on"
set-option -g @easyjump-label-chars "fjdkslaghrueiwoqptyvncmxzb1234567890"
set-option -g @easyjump-label-attrs "\e[1m\e[38;5;172m"
set-option -g @easyjump-text-attrs "\e[0m\e[38;5;237m"
```

## Integration with Vim

`easyjump.tmux` moves the cursor in Vim by simulating mouse clicks. So it's **important** to ensure the mouse is enabled in Vim.

Add to `~/.vimrc` to enable the mouse:

```vim
set mouse=a
```

### Demonstration in Vim

📹: https://asciinema.org/a/372879

### Installation in Vim

- [vim-plug](https://github.com/junegunn/vim-plug)

  1. Add to `~/.vimrc`:

    ```viml
    Plug 'roy2220/easyjump.tmux'
    ```

  2. Just `:PlugInstall`

- Manual

  1. Fetch the source:

     ```sh
     git clone https://github.com/roy2220/easyjump.tmux.git /PATH/TO/DIR
     ```

  2. Add to `~/.vimrc`:

     ```viml
     source /PATH/TO/DIR/plugin/easyjump.vim
     ```

  3. Reload Vim configuration:

     ```viml
     :source ~/.vimrc
     ```
### Usage in Vim

- Press <kbd>Ctrl</kbd> + <kbd>j</kbd> to invoke EasyJump in `normal mode` or `insert mode`.
- Press <kbd>Enter</kbd> to cancel EasyJump.

### Configuration in Vim

defaults:

```viml
let g:easyjump_smart_case = v:true
let g:easyjump_label_chars = 'fjdkslaghrueiwoqptyvncmxzb1234567890'
let g:easyjump_label_attrs = "\e[1m\e[38;5;172m"
let g:easyjump_text_attrs = "\e[0m\e[38;5;237m"

nmap <C-J> <Plug>EasyJump
imap <C-J> <Plug>EasyJump
```
