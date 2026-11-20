#!/bin/zsh
cd -- "${0:A:h}"
exec python3 editor/serve.py --open
