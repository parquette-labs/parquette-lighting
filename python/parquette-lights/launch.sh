#!/bin/zsh
export PATH="/usr/local/bin:$PATH"
export PATH="/usr/local/sbin:$PATH"
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - zsh)"
poetry run server --local-ip 0.0.0.0 --entec-auto "/dev/tty.usbserial-EN264168"