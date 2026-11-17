# Claude Toc — Specification v1.0.1

> **Status:** implemented and validated on Claude Code 2.1.325
> **Language:** English · [Português](SPEC.md)

---

## 1. Overview

**Claude Toc** is a Claude Code plugin. It sends a notification to your phone when Claude:

- finishes a task;
- asks a question and waits for you;
- needs permission to run something;
- stops because of an error.

**Analogy:** it's the microwave bell. You don't need to watch the plate spin. When it's done, it beeps.

### 1.1 Problem

You give Claude Code a task and wait. Without a signal, you either stare at the screen or come back too late. If Claude stopped to ask for permission or hit an error, it sits idle until you return.

### 1.2 Goals

- Notify the phone within seconds when Claude needs you.
- Show the project, computer, duration and a summary.
- Work on Windows and Linux.
- Install with one command, no `pip install`.

### 1.3 Out of scope (v1)

- Replying to Claude from the phone.
- Notifying when **you** interrupt Claude (Esc).
- Notifying for subagents (`SubagentStop`).
- Opening GitHub when you tap the notification.
- Queueing or summarizing notifications from quiet hours.
- Timed pause (e.g. `off 2h`).
- Notifications from headless runs (`claude -p`).

---

## 2. Decisions

| Item | Decision |
|---|---|
| Display name | **Claude Toc** |
| Internal name | `toc` (commands `/toc:*`). Names starting with `claude-` are reserved for Anthropic |
| Repository | [JfmBR/Claude-Toc](https://github.com/JfmBR/Claude-Toc) |
| Channel | [ntfy](https://ntfy.sh) (free app, no account) |
| Topic | One topic for all computers |
| Language | Python 3.9+, standard library only |
| Launcher | `scripts/run.sh` finds Python on its own (`python3`, `python`, `py`) |
| Distribution | Claude Code plugin, with a marketplace in the same repository |
| Triggers | Finished, question, permission, error |
| Interrupt (Esc) | No notification |
| Minimum duration | Default: always notify (0 s). Configurable |
| Content | Project, computer, duration, summary |
| Summary | **End** of Claude's last reply |
| Computer | Hostname, with optional nickname |
| Notification language | Configurable: Portuguese (default) or English |
| Priority | ✅ normal. ❓ 🔐 ❌ high |
| Extras | Emoji per type, quiet hours, control commands |
| Quiet hours | Default: 23:00 to 07:00. Everything is discarded |
| Pause (`off`) | Until `on`. Per computer |
| License | MIT |
| Versioning | SemVer + `CHANGELOG.md` |
| CI | GitHub Actions: Windows and Linux, Python 3.9 and 3.13, plus `claude plugin validate` |
| README demo | Phone screenshot of the notifications |
| Documentation | Portuguese and English |

---

## 3. How it works

### 3.1 Flow

```
You send a prompt
   └─► UserPromptSubmit  → saves the session's start time
                           (flags the turn if the prompt is /toc:...)

Claude works...
   ├─► Opens a multiple-choice question → PreToolUse (AskUserQuestion) → ❓
   ├─► Needs permission (~6 s idle)     → Notification (permission_prompt) → 🔐
   ├─► An MCP server asks for input     → Notification (elicitation_dialog) → ❓
   ├─► API error                        → StopFailure → ❌
   └─► Finished                         → Stop
                                           ├─ /toc:... turn  → nothing
                                           ├─ ends with "?"  → ❓
                                           └─ otherwise      → ✅

You press Esc → Claude Code doesn't fire Stop → nothing
```

### 3.2 Hooks

| Event | Matcher | Mode | Purpose |
|---|---|---|---|
| `UserPromptSubmit` | — | sync, 5 s | Save the start time |
| `Stop` | — | `async` | Send ✅ or ❓ |
| `StopFailure` | — (all errors) | `async` | Send ❌ |
| `Notification` | `permission_prompt\|elicitation_dialog` | `async` | Send 🔐 or ❓ |
| `PreToolUse` | `AskUserQuestion` | `async` | Send ❓ with the question text |

**Why not `idle_prompt`:** it fires ~60 s after a `Stop`. It would duplicate notifications.

**Why `async`:** sending never delays Claude. An async hook can't block anything, so it can't hang the session.

### 3.3 Decision rules (in order)

The first rule that blocks ends the flow.

1. **Plugin paused** (`/toc:off`) → don't send.
2. **Quiet hours** → don't send. Applies to **all** types.
3. **Plugin's own command** (`Stop` only) → if the turn's prompt started with `/toc:`, don't send.
4. **Minimum duration** (only ✅ and ❓ from `Stop`) → if the duration is shorter than the minimum, or unknown, don't send.
5. **Send** the notification.

> 🔐 and ❌ ignore the minimum duration. They block Claude, so they're always worth a notification.
> Interrupts (Esc) need no rule: Claude Code doesn't fire `Stop` when you interrupt.

### 3.4 Question detection (heuristic)

- Take the **last two paragraphs** of `last_assistant_message`, without code blocks. A list counts as part of the paragraph above it (they are the question's options).
- It's ❓ if, in that part (600 characters at most):
  - a sentence ends with `?` and the next sentence isn't its answer ("Why? Because…"); or
  - there's a request for a reply: "let me know", "reply with", "which one", "me diga", "responda com"…
- Otherwise → ✅.
- **Why not just the last character:** in real tests Claude asks and then explains how to answer ("Which do you prefer? If X, tell me which…"), or lists options after the question. Version 1.0.0 only checked the end and marked these as ✅.
- **Limitation:** Claude sometimes ends with a polite "Want me to do X?". That arrives as ❓. This is acceptable.

---

## 4. Notification content

### 4.1 Format (JSON body sent to ntfy)

| Field | Content | Example |
|---|---|---|
| `topic` | `ntfy_topic` option | `toc-3f9a1c7e5b2d4f60` |
| `title` | Type + project | `Finished · bakery-app` |
| `message` | Line 1: duration and computer. Line 2: detail | `4 min 32 s · NOTEBOOK`<br>`…all tests pass. Want me to deploy?` |
| `tags` | Emoji shortcode. ntfy shows the emoji before the title | `["white_check_mark"]` |
| `priority` | Per type | `3` |

The emoji goes in `tags`, not in the title. In both places, the app would show it twice.

### 4.2 Types

| Type | Emoji (tag) | Title (pt) | Title (en) | Priority | Line 2 |
|---|---|---|---|---|---|
| Finished | ✅ `white_check_mark` | `Terminou` | `Finished` | 3 | Summary |
| Question | ❓ `question` | `Pergunta` | `Question` | 4 | Summary, or question text |
| Permission | 🔐 `closed_lock_with_key` | `Precisa de permissão` | `Needs permission` | 4 | Event `message` field |
| Error | ❌ `x` | `Parou com erro` | `Stopped with error` | 4 | Error type, translated |
| Test | 🔔 `bell` | `Teste` | `Test` | 3 | Fixed sentence |

### 4.3 Where each value comes from

| Value | Source |
|---|---|
| Project | Git root found from `cwd` (walks up looking for `.git`). Without git, the `cwd` folder name |
| Computer | `device_name` option. If empty, `socket.gethostname()` |
| Duration | Event time minus the time saved by `UserPromptSubmit` for the same `session_id` |
| Summary | **End** of `last_assistant_message`: no markdown, collapsed spaces, last `summary_length` characters, starting at a whole word, with a leading `…` if cut |
| Question (`AskUserQuestion`) | `tool_input.questions[0].question` |
| Error type | `error` field of `StopFailure` (`rate_limit`, `overloaded`, `server_error`…), translated. Unknown values become "Unknown error" |

### 4.4 Duration format

| Duration | Display |
|---|---|
| < 60 s | `42 s` |
| < 1 h | `4 min 32 s` |
| ≥ 1 h | `1 h 05 min` |
| Unknown | line 1 shows only the computer |

The duration is unknown when the plugin was installed mid-session.

---

## 5. Configuration

### 5.1 Plugin options (`userConfig`)

Claude Code asks for these when the plugin is enabled. Change them later with `/plugin configure toc@toc`. **Sensitive** options live in the system credential store, not in `settings.json`, and don't show as `/config` rows. Claude Code still exports them to hooks (tested).

| Key | Type | Default | Description |
|---|---|---|---|
| `ntfy_topic` | string, sensitive | — (required) | Topic name. Only unaccented letters, digits, `-` and `_` (up to 64). Make it random |
| `ntfy_server` | string | `https://ntfy.sh` | ntfy server |
| `ntfy_token` | string, sensitive | empty | Access token (`tk_...`), sent as `Authorization: Bearer` |
| `python_command` | string | empty (auto) | Only if Python 3.9+ has another name |
| `device_name` | string | empty (hostname) | Computer nickname |
| `language` | string | `pt` | `pt` or `en` |
| `min_duration_seconds` | number | `0` | Minimum duration for ✅ and ❓ |
| `quiet_start` | string `HH:MM` | `23:00` | Quiet hours start |
| `quiet_end` | string `HH:MM` | `07:00` | Quiet hours end |
| `include_summary` | boolean | `true` | Turn off to keep Claude's text out of ntfy |
| `summary_length` | number | `150` | Maximum summary size (20 to 1000) |

Rules:
- `quiet_start` equal to `quiet_end` → quiet hours off.
- Quiet hours may cross midnight (23:00 → 07:00).
- Times use the computer's local clock.
- Invalid value → default is used and a warning goes to the log.

### 5.2 How the script receives options

| Source | When | Priority |
|---|---|---|
| `CLAUDE_PLUGIN_OPTION_<KEY>` variables | Hooks (exported by Claude Code) | 1st |
| `--set key=value` arguments | Manual use | 2nd |
| `config.json` in the data directory | `/toc:*` commands | 3rd |
| Script defaults | Option not set | last |

Each hook saves the options it received to `config.json`. The `/toc:*` commands run through the Bash tool, which doesn't get those variables, so they read this file. Typing `/toc:test` already fires `UserPromptSubmit`, which refreshes the file before the command runs.

**Why the script has its own defaults:** Claude Code doesn't substitute `${user_config.KEY}` when an option is left at its default. So no hook depends on that substitution.

### 5.3 Internal state

Kept in `${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/toc-toc/`), which survives plugin updates:

```
toc-toc/
├── state.json          # { "enabled": true }
├── config.json         # copy of the options, for /toc:* commands
├── starts/
│   └── <session_id>    # { "time": ..., "skip": false }
└── claude-toc.log      # errors, rotated at 100 KB
```

- One file per session in `starts/` avoids conflicts between parallel sessions.
- Files older than 24 h are deleted on every new prompt.
- `enabled` is per computer.

---

## 6. Control commands

They are plugin *skills* with `disable-model-invocation: true`: only you invoke them, Claude never does.

| Command | Action |
|---|---|
| `/toc:test` | Sends a test notification now. Ignores quiet hours and pause |
| `/toc:off` | Pauses notifications on this computer until `on` |
| `/toc:on` | Resumes notifications |
| `/toc:status` | Shows state, topic (masked), server, computer, language, minimum duration, quiet hours and summary |

Each command asks Claude to run `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <command> --data-dir "${CLAUDE_PLUGIN_DATA}"` and show the output. A `/toc:` turn doesn't send a notification.

---

## 7. User warnings

### 7.1 Quiet hours ⚠️

> **During quiet hours, no notification is sent. That includes questions, permission requests and errors.**
> If Claude asks for something in that window, it waits, and you are **not** notified. The message is discarded, not queued.

This warning appears in the README and in `/toc:status` output while quiet hours are active.

### 7.2 Security and privacy 🔒

**Threat model.** On the public server the topic is the only protection: whoever knows the name reads and sends notifications. A topic like `joao` collides with other people.

| Risk | Protection in the plugin | Advice to the user |
|---|---|---|
| Guessable topic | `/toc:status` and `/toc:test` warn when the topic is under 16 characters or has no digit (unless a token is set) | Generate it with `python -c "import secrets; print('toc-' + secrets.token_hex(16))"` |
| Invalid topic (e.g. accents) | The hook doesn't send and logs it; `/toc:test` shows the error | Only `A-Z a-z 0-9 - _` |
| Shared or exposed topic | `ntfy_token` option → `Authorization: Bearer tk_...` | Own server, or a reserved topic on ntfy.sh |
| Secrets in sent text | `redact_secrets` replaces them with `[•••]`: `sk-`, `ghp_`/`github_pat_`, `AKIA`, `xox*-`, `AIza`, `tk_` keys, JWTs, PEM private keys, `password=`/`token:`/`api_key=`, `Bearer`/`Basic`, `user:pass@` URLs | `include_summary: false` to send no text |
| Topic and token on disk | Sensitive options in the system credential store. Data folder `0700`, files `0600` | — |
| Unencrypted network | Warning for `http://` outside `localhost` | Use `https://` |
| A hook stalling or steering Claude | Async hooks, always `exit 0`, nothing on stdout | — |
| Command injection | The hook command only uses a quoted `${CLAUDE_PLUGIN_ROOT}`. No user option reaches the command line. `session_id` is sanitized before it becomes a file name | — |
| CI | GitHub Actions token is read-only (`contents: read`) | — |

The secret filter is a safety net, not a guarantee.

### 7.3 Native push

If you also enable Claude Code's Remote Control push in `/config`, you get **two** notifications. Use only one.

---

## 8. Technical requirements

### 8.1 Launcher `run.sh`

- POSIX shell. Runs on Linux, macOS and Git Bash on Windows.
- Tries, in order: `python_command` (if set), `python3`, `python`, `py`.
- Accepts only a Python that passes `sys.version_info >= (3, 9)`. This skips the Microsoft Store alias, which exists but doesn't work.
- Reads the hook JSON once and passes it to Python.
- Always exits 0.

### 8.2 Script `toc.py`

- **Hook subcommands** (JSON on stdin): `start`, `stop`, `failure`, `notify`, `ask`.
- **Control subcommands:** `test`, `on`, `off`, `status`. They accept `--data-dir` and `--set key=value`.
- **Sending:** `urllib.request`, `POST` with a JSON body to the server root. JSON avoids accent problems in HTTP headers.
- **Network timeout:** 5 s.
- **Texts:** `pt`/`en` dictionary inside the script.
- **Hooks never write to stdout.** A `UserPromptSubmit` hook's stdout would be added to Claude's context.
- **Hooks always exit 0.**

> ⚠️ **Never exit with code 2 on `Stop`.** Per the official docs, exit 2 on `Stop` makes Claude keep working. Every error is caught, logged and ends with `exit 0`.

### 8.3 Hook configuration

Shell form (`command` without `args`), because `sh` needs a shell on Windows:

```json
{
  "type": "command",
  "command": "sh \"${CLAUDE_PLUGIN_ROOT}/scripts/run.sh\" stop",
  "async": true
}
```

The full file is `hooks/hooks.json`.

### 8.4 Repository layout

```
Claude-Toc/
├── .claude-plugin/
│   ├── plugin.json         # name "toc", displayName "Claude Toc", userConfig
│   └── marketplace.json    # marketplace "toc", plugin at the root ("./")
├── .github/workflows/
│   └── tests.yml           # tests + launcher + claude plugin validate
├── hooks/
│   └── hooks.json
├── skills/
│   ├── test/SKILL.md
│   ├── on/SKILL.md
│   ├── off/SKILL.md
│   └── status/SKILL.md
├── scripts/
│   ├── run.sh              # finds Python
│   └── toc.py              # all the logic
├── tests/
│   └── test_toc.py         # unittest, no dependencies
├── docs/
│   ├── SPEC.md
│   ├── SPEC.en.md
│   └── images/             # notification screenshots
├── README.md               # English
├── README.pt-br.md
├── CHANGELOG.md
├── .gitignore
└── LICENSE                 # MIT
```

### 8.5 Installation

In one step, from a terminal (Claude Code 2.1.275+):

```bash
claude plugin install toc --marketplace JfmBR/Claude-Toc --config ntfy_topic=YOUR-TOPIC
```

Or inside Claude Code:

```
/plugin marketplace add JfmBR/Claude-Toc
/plugin install toc@toc
```

The repository must be **public** for others to install it.

### 8.6 Compatibility

| System | Requirement |
|---|---|
| Linux | Python 3.9+ |
| Windows | Python 3.9+ and Git for Windows (provides `sh`) |
| macOS | Python 3.9+ (not a focus, but should work) |

The minimum moved from 3.8 to 3.9: Python 3.8 has been end-of-life since October 2024, and 3.9 was tested here.

### 8.7 Versioning

- SemVer: `MAJOR.MINOR.PATCH`. First version: `1.0.0`.
- `plugin.json` version matches the git tag (`v1.0.0`). Bumping it is what delivers the update to users.
- `CHANGELOG.md` follows *Keep a Changelog*.

---

## 9. Validation done

The six open points from the previous spec were resolved as follows:

| # | Point | Result |
|---|---|---|
| 1 | Question box (`AskUserQuestion`) | Doesn't produce a `Notification`. Fix: `PreToolUse` hook matching `AskUserQuestion`, which sends the question text |
| 2 | `${user_config.*}` in `command` | **Fails** when the option is left at its default: the hook doesn't run. Fix: `run.sh` launcher and options read from environment variables |
| 3 | Command names | Prefixed with the plugin name: `/toc:test`. The name `claude-toc` is reserved and became `toc` |
| 4 | `async` receives the full JSON | Yes, per the official docs. But in `claude -p`, Claude Code cancels async hooks on exit |
| 5 | `Stop` on Esc | Doesn't fire, per the official docs. The interrupt rule needs no code |
| 6 | `StopFailure` fields | `error` (type), `error_details` and `last_assistant_message` |

### 9.1 End-to-end test

Run on a real Claude Code 2.1.325, with the plugin installed from a local marketplace and a fake ntfy server:

- Prompt in a subfolder of a git repo → received `Pergunta · meu-projeto`, `4 s · SANDBOX`, with the end of the reply.
- `/toc:status`, `/toc:test`, `/toc:off`, `/toc:on` → correct output. Only `test` sent a notification.
- `/toc:off` → the next `Stop` sent nothing.

---

## 10. Test plan

### 10.1 Automated tests (`unittest`, 45 cases)

| Area | Cases |
|---|---|
| Quiet hours | Inside, outside, across midnight, start = end |
| Duration | 42 s, 4 min 32 s, 1 h 05 min, no start |
| Question detection | Ends with `?`, with `?` + markdown, without `?`, empty text |
| Summary | Tail cut, starts at a whole word, `…`, markdown removal |
| Project name | Subfolder of a git repo, folder without git |
| Configuration | Defaults, invalid values, source priority, language |
| Decision | Pause and quiet hours block everything; minimum duration; 🔐 and ❌ ignore the minimum; `AskUserQuestion`; summary off |
| End to end | Full turn against a fake server; hook never fails (network down, invalid JSON); `off`/`on`/`test`/`status`; `/toc:` commands don't notify; quiet-hours warning in `status`; old file cleanup |

### 10.2 CI (GitHub Actions)

- `python -m unittest` on `ubuntu-latest` and `windows-latest`, Python 3.9 and 3.13.
- `run.sh` smoke test through Git Bash (on Windows, it confirms Python is found).
- `claude plugin validate .` with the current Claude Code.

### 10.3 Manual tests (on your computer)

- [ ] Windows: short task → ✅ with duration.
- [ ] Linux: short task → ✅ with duration.
- [ ] Permission prompt left ~6 s → 🔐.
- [ ] Multiple-choice question → ❓ with its text.
- [ ] `language: en` → English texts.
- [ ] Quiet hours active → nothing arrives, `/toc:status` shows the warning.
- [ ] Notebook and PC on the same topic → each notification shows the right computer.

---

## 11. Future ideas (v2+)

- Tapping the notification opens the GitHub repository (ntfy `click` field).
- Timed pause (`/toc:off 2h`).
- Quiet-hours queue with a summary at 07:00.
- Telegram and Discord as alternative channels.
- Windows support without Git Bash (PowerShell launcher).
- Plugin icon (`.claude-plugin/icon.png`).

---

## 12. References

- [Hooks reference — Claude Code](https://code.claude.com/docs/en/hooks)
- [Plugin manifest reference — Claude Code](https://code.claude.com/docs/en/plugins/manifest-reference)
- [Marketplace reference — Claude Code](https://code.claude.com/docs/en/plugins/marketplace-reference)
- [ntfy — documentation](https://docs.ntfy.sh)
