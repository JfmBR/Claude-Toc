#!/bin/sh
# Claude Toc launcher: finds a working Python 3.9+ and runs toc.py.
# Order: the "python_command" plugin option, then python3, python, py.
# Always exits 0 so a hook can never block Claude.

script_dir=$(cd "$(dirname "$0")" && pwd)

case "$1" in
  start|stop|failure|notify|ask) input=$(cat) ;;   # hook JSON on stdin
  *) input="" ;;
esac

for py in "$CLAUDE_PLUGIN_OPTION_PYTHON_COMMAND" python3 python py; do
  [ -n "$py" ] || continue
  if "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    printf '%s' "$input" | "$py" "$script_dir/toc.py" "$@"
    exit 0
  fi
done

echo "Claude Toc: Python 3.9+ not found (tried python3, python, py)." >&2
exit 0
