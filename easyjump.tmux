#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail # -o xtrace

KEY_BINDING=$(get_tmux_option @easyjump-key-binding '')
[[ -z ${KEY_BINDING} ]] && KEY_BINDING=j

CURRENT_DIR="$(dirname $(realpath "${0}"))"

LABEL_CHARS=$(get_tmux_option @easyjump-label-chars '')
[[ -z ${LABEL_CHARS} ]] && LABEL_CHARS=fjdkslaghrueiwoqptyvncmxzb1234567890

LABEL_ATTRS=$(get_tmux_option @easyjump-label-attrs '')
[[ -z ${LABEL_ATTRS} ]] && LABEL_ATTRS='\e[1m\e[38;5;172m'
LABEL_ATTRS=$(echo -e "${LABEL_ATTRS}")

TEXT_ATTRS=$(get_tmux_option @easyjump-text-attrs '')
[[ -z ${TEXT_ATTRS} ]] && TEXT_ATTRS='\e[0m\e[38;5;237m'
TEXT_ATTRS=$(echo -e "${TEXT_ATTRS}")

tmux bind-key "${KEY_BINDING}" run-shell -b "python3 ${CURRENT_DIR@Q}/easyjump.py ${LABEL_CHARS@Q} ${LABEL_ATTRS@Q} ${TEXT_ATTRS@Q}"
