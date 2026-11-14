# Claude Toc 🔔

[![tests](https://github.com/JfmBR/Claude-Toc/actions/workflows/tests.yml/badge.svg)](https://github.com/JfmBR/Claude-Toc/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**English** · [Português](README.pt-br.md)

A Claude Code plugin that sends a push notification to your phone when Claude:

- ✅ finishes a task;
- ❓ asks you a question;
- 🔐 needs your permission to run something;
- ❌ stops because of an error (usage limit, server down…).

Think of it as the microwave bell: you don't need to watch the plate spin. When it's done, it beeps.

Notifications go through [ntfy](https://ntfy.sh), a free push app that needs no account. Each one shows the project, the computer, how long Claude worked, and the end of its last reply.

<!-- Screenshot: add docs/images/notifications.png and uncomment the line below.
![Claude Toc notifications on a phone](docs/images/notifications.png)
-->

## Install

**1. Phone.** Install the **ntfy** app ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) · [iOS](https://apps.apple.com/app/ntfy/id1625396347)) and subscribe to a topic with a long, random name, such as `toc-yourname-8f3k2m9q`.

**2. Claude Code.** In your terminal:

```bash
claude plugin install toc --marketplace JfmBR/Claude-Toc --config ntfy_topic=toc-yourname-8f3k2m9q
```

Or inside Claude Code:

```
/plugin marketplace add JfmBR/Claude-Toc
/plugin install toc@toc
```

Claude Code asks for the plugin options. Only `ntfy_topic` is required.

**3. Test.** Run `/toc:test` in Claude Code. Your phone should ring.

Use the **same topic** on all your computers. The notification tells you which computer it came from.

## What each notification looks like

| Type | When | Priority | Second line |
|---|---|---|---|
| ✅ Finished | Claude ends its reply | normal | End of Claude's reply |
| ❓ Question | The end of the reply asks you something, or Claude opens a multiple-choice question | high | The question |
| 🔐 Needs permission | A permission prompt waits about 6 s without you typing | high | What Claude wants to run |
| ❌ Stopped with error | The turn ends with an API error | high | The error type |

Example:

```
✅ Finished · bakery-app
4 min 32 s · NOTEBOOK
…all 18 tests pass. Want me to open the pull request?
```

## Commands

| Command | What it does |
|---|---|
| `/toc:test` | Sends a test notification now. Ignores pause and quiet hours |
| `/toc:off` | Pauses notifications on this computer until `/toc:on` |
| `/toc:on` | Resumes notifications |
| `/toc:status` | Shows the settings and whether quiet hours are active now |

These commands never trigger a notification themselves.

## Options

Change them with `/config` in Claude Code, or with `claude plugin configure toc@toc`.

| Option | Default | What it does |
|---|---|---|
| `ntfy_topic` | — (required) | Topic your phone subscribes to |
| `ntfy_server` | `https://ntfy.sh` | Your own ntfy server, if you have one |
| `device_name` | hostname | Computer nickname, such as `Notebook` or `PC` |
| `language` | `pt` | Notification language: `pt` or `en` |
| `min_duration_seconds` | `0` | Skip ✅ and ❓ for turns shorter than this. 🔐 and ❌ always go out |
| `quiet_start` / `quiet_end` | `23:00` / `07:00` | Quiet hours, in local time. Same value = off |
| `include_summary` | `true` | Send the end of Claude's reply |
| `summary_length` | `150` | Maximum summary size, in characters |
| `python_command` | auto | Python 3.9+ command. Leave empty: it tries `python3`, `python` and `py` |

### ⚠️ Quiet hours

During quiet hours **no notification is sent, not even questions or permission requests.** If Claude asks for something in that window, it waits, and you are **not** told. The notification is discarded, not queued. `/toc:status` shows this warning while quiet hours are active.

### 🔒 Privacy

- The public `ntfy.sh` server has no password. **Anyone who knows your topic can read your notifications.** Use a long, random topic.
- The summary sends part of Claude's reply to the ntfy server. It can include file names, code or project details.
- For more privacy, set `include_summary` to `false`, or point `ntfy_server` at your own ntfy server.

## Requirements

- Claude Code with plugin support.
- Python 3.9 or newer. No packages to install.
- `sh`: built into Linux and macOS. On Windows, it comes with [Git for Windows](https://git-scm.com/downloads/win) (Git Bash), which Claude Code uses anyway.

## Limitations

- **Question detection is a heuristic.** It reads the last two paragraphs of the reply. A polite "Want me to do X?" at the end arrives as ❓, not ✅.
- **No notification when you press Esc.** Claude Code doesn't fire the `Stop` event on an interrupt. That's on purpose: you are at the computer.
- **Headless runs (`claude -p`) don't notify.** The notification hooks run in the background, and Claude Code cancels background hooks when a `-p` run exits.
- **Native push.** If you also turn on Claude Code's own Remote Control push in `/config`, you get two notifications. Use one or the other.

## Troubleshooting

1. Run `/toc:status` and check the topic and server.
2. Run `/toc:test`. If it fails, the error appears on screen.
3. Check the log: `~/.claude/plugins/data/toc-toc/claude-toc.log`.
4. Check that the phone is subscribed to exactly the same topic.

## How it works

The plugin registers [Claude Code hooks](https://code.claude.com/docs/en/hooks) that call `scripts/toc.py`:

| Hook | Use |
|---|---|
| `UserPromptSubmit` | Saves when the turn started, to show the duration |
| `Stop` | ✅ or ❓ |
| `StopFailure` | ❌ |
| `Notification` (`permission_prompt`, `elicitation_dialog`) | 🔐 or ❓ |
| `PreToolUse` (`AskUserQuestion`) | ❓ |

The script uses only the Python standard library and never blocks Claude: every hook exits with code 0. The full design is in [docs/SPEC.en.md](docs/SPEC.en.md).

## Development

```bash
python -m unittest discover -s tests -v
claude plugin validate .
```

CI runs the tests on Linux and Windows, with Python 3.9 and 3.13. See [CHANGELOG.md](CHANGELOG.md) for versions.

## License

[MIT](LICENSE) © João Francisco
