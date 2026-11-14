---
name: status
description: Show Claude Toc settings and whether quiet hours are active
disable-model-invocation: true
allowed-tools: Bash
---

Run this exact command with the Bash tool, then show its output to the user word for word, with no commentary:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" status --data-dir "${CLAUDE_PLUGIN_DATA}"
```

If the output says Python was not found, tell the user to install Python 3.9 or newer, or to set the plugin option "Python command" in /config.

On Windows this needs Git for Windows (Git Bash), which provides `sh`.