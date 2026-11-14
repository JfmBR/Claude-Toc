# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-11-14

### Fixed

- Questions written as plain text now arrive as ❓. Detection reads the last two paragraphs, so it catches a question followed by options, an emoji, or instructions such as "let me know" / "me diga qual". Version 1.0.0 only checked whether the reply's last character was `?`.
- Control commands always print UTF-8, so accents show correctly on Windows.

## [1.0.0] - 2026-11-14

### Added

- Phone notifications through [ntfy](https://ntfy.sh) when Claude Code:
  - ✅ finishes a task (`Stop`);
  - ❓ asks a question (reply ending in `?`, `AskUserQuestion`, MCP input request);
  - 🔐 needs permission (`permission_prompt`);
  - ❌ stops with an API error (`StopFailure`).
- Notification shows project, computer, duration and the end of Claude's reply.
- Commands `/toc:test`, `/toc:on`, `/toc:off` and `/toc:status`.
- Options: topic, server, computer nickname, language (`pt`/`en`), minimum duration, quiet hours, summary on/off and length.
- `run.sh` launcher that finds Python 3.9+ (`python3`, `python`, `py`).
- Tests with the standard library and CI on Linux and Windows.
- Documentation in English and Portuguese.

[1.0.1]: https://github.com/JfmBR/Claude-Toc/releases/tag/v1.0.1
[1.0.0]: https://github.com/JfmBR/Claude-Toc/releases/tag/v1.0.0
