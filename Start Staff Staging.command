#!/bin/zsh
cd -- "${0:A:h}"
if [[ -x ../../work/backend-venv/bin/python ]]; then
  olv_runtime=../../work/backend-venv/bin/python
else
  olv_runtime=.venv/bin/python
fi
if [[ ! -x "$olv_runtime" ]]; then
  python3 -m venv .venv || exit 1
  .venv/bin/python -m pip install -r editor/backend/requirements.txt || exit 1
fi
print 'Open http://127.0.0.1:4180/ in your browser. Keep this window open.'
exec "$olv_runtime" -m editor.backend.server
