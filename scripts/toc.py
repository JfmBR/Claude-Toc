#!/usr/bin/env python3
"""Claude Toc: push notifications to your phone (via ntfy) for Claude Code.

Subcommands
-----------
Hook handlers (read the hook JSON from stdin):
    start     UserPromptSubmit  -> remember when the turn started
    stop      Stop              -> "finished" or "question"
    failure   StopFailure       -> "error"
    notify    Notification      -> "permission" or "question"
    ask       PreToolUse (AskUserQuestion) -> "question"

Control commands (run from the plugin skills):
    test      send a test notification now (ignores pause and quiet hours)
    on        resume notifications on this computer
    off       pause notifications on this computer
    status    show the current configuration

Only the Python standard library is used. Hook handlers ALWAYS exit 0:
exit code 2 on a Stop hook would make Claude keep working.
"""

import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

VERSION = "1.0.1"

# --------------------------------------------------------------------------
# Defaults and configuration
# --------------------------------------------------------------------------

DEFAULTS = {
    "ntfy_topic": "",
    "ntfy_server": "https://ntfy.sh",
    "ntfy_token": "",
    "device_name": "",
    "language": "pt",
    "min_duration_seconds": 0,
    "quiet_start": "23:00",
    "quiet_end": "07:00",
    "include_summary": True,
    "summary_length": 150,
}

NETWORK_TIMEOUT = 5          # seconds
START_FILE_MAX_AGE = 24 * 3600
LOG_MAX_BYTES = 100 * 1024

# ntfy accepts letters, digits, "_" and "-", up to 64 characters.
TOPIC_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
WEAK_TOPIC_MIN_LENGTH = 16

HOOK_COMMANDS = ("start", "stop", "failure", "notify", "ask")
CONTROL_COMMANDS = ("test", "on", "off", "status")

# --------------------------------------------------------------------------
# Texts (pt / en)
# --------------------------------------------------------------------------

TEXTS = {
    "pt": {
        "finished": "Terminou",
        "question": "Pergunta",
        "permission": "Precisa de permissão",
        "error": "Parou com erro",
        "test": "Teste",
        "test_message": "Se você está lendo isto, o Claude Toc funciona.",
        "on": "Claude Toc ligado neste computador.",
        "off": "Claude Toc pausado neste computador. Use /toc:on para religar.",
        "no_topic": "Erro: nenhum tópico do ntfy configurado (opção ntfy_topic).",
        "bad_topic": "Erro: o tópico só pode ter letras sem acento, números, - e _ (até 64).",
        "weak_topic": (
            "Atenção: seu tópico é fácil de adivinhar. Qualquer pessoa que assinar "
            "o mesmo nome lê seus avisos. Use um nome longo e aleatório (16+ "
            "caracteres, com números) ou um token de acesso (opção ntfy_token)."
        ),
        "insecure_server": "Atenção: o servidor usa http://, sem criptografia. Prefira https://.",
        "status_token": "Token de acesso",
        "token_set": "configurado",
        "token_unset": "não configurado",
        "sent": "Notificação de teste enviada para o tópico {topic}.",
        "send_failed": "Falha ao enviar: {error}",
        "status_title": "Claude Toc v{version}",
        "status_state": "Estado",
        "state_on": "ligado",
        "state_off": "pausado",
        "status_topic": "Tópico",
        "status_server": "Servidor",
        "status_device": "Computador",
        "status_language": "Idioma",
        "status_min": "Tempo mínimo",
        "status_quiet": "Horário silencioso",
        "quiet_disabled": "desligado",
        "quiet_now": "ATIVO AGORA",
        "status_summary": "Resumo",
        "summary_on": "ligado ({n} caracteres)",
        "summary_off": "desligado",
        "quiet_warning": (
            "Aviso: durante o horário silencioso nenhum aviso é enviado, "
            "nem perguntas nem pedidos de permissão. Se o Claude pedir algo "
            "agora, ele vai esperar e você não será avisado."
        ),
        "errors": {
            "rate_limit": "Limite de uso atingido",
            "overloaded": "Servidor sobrecarregado",
            "authentication_failed": "Falha de autenticação",
            "oauth_org_not_allowed": "Organização não permitida",
            "account_on_hold": "Conta suspensa",
            "billing_error": "Problema de cobrança",
            "invalid_request": "Requisição inválida",
            "model_not_found": "Modelo não encontrado",
            "server_error": "Erro no servidor",
            "max_output_tokens": "Resposta longa demais",
            "cloud_credential_error": "Erro de credencial na nuvem",
            "unknown": "Erro desconhecido",
        },
    },
    "en": {
        "finished": "Finished",
        "question": "Question",
        "permission": "Needs permission",
        "error": "Stopped with error",
        "test": "Test",
        "test_message": "If you can read this, Claude Toc works.",
        "on": "Claude Toc is on for this computer.",
        "off": "Claude Toc is paused on this computer. Use /toc:on to resume.",
        "no_topic": "Error: no ntfy topic configured (ntfy_topic option).",
        "bad_topic": "Error: the topic may only have letters, digits, - and _ (up to 64).",
        "weak_topic": (
            "Warning: your topic is easy to guess. Anyone who subscribes to the "
            "same name reads your notifications. Use a long random name (16+ "
            "characters, with digits) or an access token (ntfy_token option)."
        ),
        "insecure_server": "Warning: the server uses http://, without encryption. Prefer https://.",
        "status_token": "Access token",
        "token_set": "set",
        "token_unset": "not set",
        "sent": "Test notification sent to topic {topic}.",
        "send_failed": "Failed to send: {error}",
        "status_title": "Claude Toc v{version}",
        "status_state": "State",
        "state_on": "on",
        "state_off": "paused",
        "status_topic": "Topic",
        "status_server": "Server",
        "status_device": "Computer",
        "status_language": "Language",
        "status_min": "Minimum duration",
        "status_quiet": "Quiet hours",
        "quiet_disabled": "off",
        "quiet_now": "ACTIVE NOW",
        "status_summary": "Summary",
        "summary_on": "on ({n} characters)",
        "summary_off": "off",
        "quiet_warning": (
            "Warning: during quiet hours no notification is sent, not even "
            "questions or permission requests. If Claude asks for something "
            "now, it will wait and you will not be notified."
        ),
        "errors": {
            "rate_limit": "Usage limit reached",
            "overloaded": "Server overloaded",
            "authentication_failed": "Authentication failed",
            "oauth_org_not_allowed": "Organization not allowed",
            "account_on_hold": "Account on hold",
            "billing_error": "Billing problem",
            "invalid_request": "Invalid request",
            "model_not_found": "Model not found",
            "server_error": "Server error",
            "max_output_tokens": "Response too long",
            "cloud_credential_error": "Cloud credential error",
            "unknown": "Unknown error",
        },
    },
}

# kind -> (ntfy emoji tag, ntfy priority)
KINDS = {
    "finished": ("white_check_mark", 3),
    "question": ("question", 4),
    "permission": ("closed_lock_with_key", 4),
    "error": ("x", 4),
    "test": ("bell", 3),
}

# --------------------------------------------------------------------------
# Small pure helpers (unit tested)
# --------------------------------------------------------------------------


def parse_bool(value, default):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on", "sim", "s"):
        return True
    if text in ("0", "false", "no", "n", "off", "nao", "não"):
        return False
    return default


def parse_int(value, default, minimum=None, maximum=None):
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number


def parse_hhmm(value):
    """'23:00' -> 1380 (minutes since midnight). Returns None if invalid."""
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(value or ""))
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def in_quiet_hours(now_minutes, start, end):
    """True if now is inside [start, end). Handles ranges across midnight."""
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= now_minutes < end
    return now_minutes >= start or now_minutes < end


def format_duration(seconds):
    if seconds is None or seconds < 0:
        return None
    seconds = int(round(seconds))
    if seconds < 60:
        return "{} s".format(seconds)
    if seconds < 3600:
        return "{} min {} s".format(seconds // 60, seconds % 60)
    hours, rest = divmod(seconds, 3600)
    return "{} h {:02d} min".format(hours, rest // 60)


_MD_PATTERNS = [
    (re.compile(r"```.*?```", re.S), " "),          # fenced code blocks
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),  # images
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),   # links
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),    # headings
    (re.compile(r"^\s{0,3}>\s?", re.M), ""),         # quotes
    (re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.M), ""),  # list markers
    (re.compile(r"^\s*\|?[-:| ]{3,}\|?\s*$", re.M), " "),  # table rules
    (re.compile(r"(\*\*|__|~~|`)"), ""),             # emphasis, code
    (re.compile(r"(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)"), ""),  # *x* _x_
]


def strip_markdown(text):
    text = text or ""
    for pattern, replacement in _MD_PATTERNS:
        text = pattern.sub(replacement, text)
    text = text.replace("|", " ")
    return re.sub(r"\s+", " ", text).strip()


_LIST_LINE = re.compile(r"^\s*(?:[-*+•]|\d+[.)]|[a-zA-Z][.)])\s+\S")
_SENTENCE_END = re.compile(r"(?<=[.!?？…])\s+")
_ANSWER_START = re.compile(r"^(porque|pois|because|resposta|answer)\b", re.I)
_ASK_CUE = re.compile(
    r"\b(?:me\s+(?:diga|diz|avise|avisa|conte|conta|fale|fala|responda|confirme|confirma)"
    r"|responda\s+com|escolha\s+(?:uma|um|entre|a\s+op)"
    r"|qual\s+(?:voc[eê]|vc)\s+prefere"
    r"|let\s+me\s+know|tell\s+me\s+(?:which|what|if|whether)"
    r"|reply\s+with|choose\s+(?:one|between|an?\s+option)|which\s+(?:one|do\s+you))\b",
    re.I)
QUESTION_TAIL_CHARS = 600


def _trim_end(text):
    """Drop trailing emoji, quotes and other symbols, keep . ! ? …"""
    while text and not (text[-1].isalnum() or text[-1] in ".!?？…:;"):
        text = text[:-1]
    return text


def _last_paragraphs(text, count=2):
    """Last `count` paragraphs; a list joins the paragraph above it."""
    raw = re.sub(r"```.*?```", "\n\n", text or "", flags=re.S)
    blocks = [b for b in re.split(r"\n\s*\n", raw) if b.strip()]
    merged = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if merged and lines and all(_LIST_LINE.match(line) for line in lines):
            merged[-1] = merged[-1] + "\n" + block
        else:
            merged.append(block)
    return merged[-count:]


def is_question(text):
    """Heuristic: does Claude's reply end by asking the user something?

    Looks at the last two paragraphs (a list of options counts as part of
    the paragraph above it). It is a question when a sentence there ends
    with "?" and is not answered right away ("Why? Because..."), or when
    it asks for a reply ("let me know", "me diga", "responda com"...).
    """
    tail = strip_markdown("\n\n".join(_last_paragraphs(text)))
    tail = tail[-QUESTION_TAIL_CHARS:]
    if not tail:
        return False
    if _ASK_CUE.search(tail):
        return True
    sentences = [x.strip() for x in _SENTENCE_END.split(tail) if x.strip()]
    for index, sentence in enumerate(sentences):
        if _trim_end(sentence).endswith(("?", "？")):
            following = sentences[index + 1] if index + 1 < len(sentences) else ""
            if not _ANSWER_START.match(following):
                return True
    return False


def summarize_tail(text, limit):
    """Last `limit` characters of the plain text, starting at a whole word."""
    clean = strip_markdown(text)
    if not clean or limit <= 0:
        return ""
    if len(clean) <= limit:
        return clean
    tail = clean[-limit:]
    space = tail.find(" ")
    if 0 <= space < len(tail) - 1:
        tail = tail[space + 1:]
    return "…" + tail


_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.S),
    re.compile(r"\b(?:sk-ant-|sk-proj-|sk-)[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\btk_[A-Za-z0-9]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b((?:api[_-]?key|access[_-]?key|secret|password|passwd|pwd|token|auth)"
    r"[A-Za-z0-9_-]*\s*[:=]\s*)([\"']?)[^\s\"',;]{4,}\2")
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_URL_CREDENTIALS = re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@", re.I)
REDACTED = "[•••]"


def redact_secrets(text):
    """Hide things that look like credentials before they leave the computer."""
    if not text:
        return text or ""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    text = _SECRET_ASSIGNMENT.sub(lambda m: m.group(1) + REDACTED, text)
    text = _BEARER.sub(lambda m: m.group(1) + " " + REDACTED, text)
    text = _URL_CREDENTIALS.sub(lambda m: m.group(1) + REDACTED + "@", text)
    return text


def is_valid_topic(topic):
    return bool(TOPIC_RE.match(topic or ""))


def is_weak_topic(topic):
    """Short or without digits: likely guessable (a name, a word)."""
    topic = topic or ""
    return len(topic) < WEAK_TOPIC_MIN_LENGTH or not any(ch.isdigit() for ch in topic)


def is_insecure_server(server):
    server = (server or "").lower()
    return server.startswith("http://") and not re.match(
        r"http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(/|$)", server)


def find_project_name(cwd):
    """Name of the git root that contains cwd, else the name of cwd."""
    if not cwd:
        return ""
    path = os.path.abspath(cwd)
    probe = path
    while True:
        if os.path.exists(os.path.join(probe, ".git")):
            return os.path.basename(probe) or probe
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return os.path.basename(path.rstrip("\\/")) or path


def mask_topic(topic):
    if not topic:
        return "-"
    if len(topic) <= 4:
        return topic[0] + "…"
    return topic[:4] + "…" + "(" + str(len(topic)) + ")"


# --------------------------------------------------------------------------
# Configuration loading
# --------------------------------------------------------------------------


class Config(object):
    def __init__(self, values, warnings):
        self.values = values
        self.warnings = warnings

    def __getitem__(self, key):
        return self.values[key]

    @property
    def lang(self):
        return self.values["language"]

    def text(self, key):
        return TEXTS[self.lang][key]


def raw_options(overrides, env, snapshot):
    """Merge option sources. Priority: env > --set overrides > snapshot."""
    raw = {}
    for key in DEFAULTS:
        env_key = "CLAUDE_PLUGIN_OPTION_" + key.upper()
        if env_key in env and str(env[env_key]).strip() != "":
            raw[key] = env[env_key]
        elif key in overrides and str(overrides[key]).strip() != "":
            raw[key] = overrides[key]
        elif key in snapshot and str(snapshot[key]).strip() != "":
            raw[key] = snapshot[key]
    return raw


def build_config(raw):
    values = dict(DEFAULTS)
    warnings = []

    for key in ("ntfy_topic", "ntfy_server", "ntfy_token", "device_name"):
        if key in raw:
            values[key] = str(raw[key]).strip()
    values["ntfy_server"] = (values["ntfy_server"] or DEFAULTS["ntfy_server"]).rstrip("/")

    lang = str(raw.get("language", DEFAULTS["language"])).strip().lower()
    lang = {"pt-br": "pt", "pt_br": "pt", "en-us": "en", "en_us": "en"}.get(lang, lang)
    if lang not in TEXTS:
        warnings.append("invalid language {!r}, using 'pt'".format(raw.get("language")))
        lang = "pt"
    values["language"] = lang

    if "min_duration_seconds" in raw:
        number = parse_int(raw["min_duration_seconds"], None, minimum=0)
        if number is None:
            warnings.append("invalid min_duration_seconds, using 0")
            number = 0
        values["min_duration_seconds"] = number

    if "summary_length" in raw:
        number = parse_int(raw["summary_length"], None, minimum=20, maximum=1000)
        if number is None:
            warnings.append("invalid summary_length, using 150")
            number = 150
        values["summary_length"] = number

    if "include_summary" in raw:
        values["include_summary"] = parse_bool(raw["include_summary"], True)

    for key in ("quiet_start", "quiet_end"):
        if key in raw:
            if parse_hhmm(raw[key]) is None:
                warnings.append("invalid {}, using {}".format(key, DEFAULTS[key]))
            else:
                values[key] = str(raw[key]).strip()

    return Config(values, warnings)


# --------------------------------------------------------------------------
# Files: data dir, state, start times, log
# --------------------------------------------------------------------------


def data_dir(explicit=None):
    path = explicit or os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        os.path.expanduser("~"), ".claude-toc")
    os.makedirs(path, mode=0o700, exist_ok=True)
    try:
        os.chmod(path, 0o700)  # only you can read it (no effect on Windows)
    except OSError:
        pass
    return path


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, type(default)) else default
    except (OSError, ValueError):
        return default


def write_json(path, value):
    """Write a private (0600) JSON file atomically."""
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def is_enabled(ddir):
    return parse_bool(read_json(os.path.join(ddir, "state.json"), {}).get("enabled"), True)


def set_enabled(ddir, enabled):
    path = os.path.join(ddir, "state.json")
    state = read_json(path, {})
    state["enabled"] = bool(enabled)
    write_json(path, state)


def safe_session_id(session_id):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id or ""))[:128]


def is_own_command(prompt):
    """True for the plugin's own commands (/toc:test, /toc:status...)."""
    return bool(re.match(r"\s*/toc:", str(prompt or "")))


def save_start(ddir, session_id, now, skip=False):
    sid = safe_session_id(session_id)
    if not sid:
        return
    folder = os.path.join(ddir, "starts")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    write_json(os.path.join(folder, sid), {"time": now, "skip": bool(skip)})


def load_start(ddir, session_id):
    """Return (start_time or None, skip_this_turn)."""
    sid = safe_session_id(session_id)
    if not sid:
        return None, False
    value = read_json(os.path.join(ddir, "starts", sid), {})
    try:
        return float(value.get("time")), bool(value.get("skip"))
    except (TypeError, ValueError):
        return None, False


def prune_starts(ddir, now):
    folder = os.path.join(ddir, "starts")
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        try:
            if now - os.path.getmtime(path) > START_FILE_MAX_AGE:
                os.remove(path)
        except OSError:
            pass


def log(ddir, message):
    try:
        path = os.path.join(ddir, "claude-toc.log")
        if os.path.exists(path) and os.path.getsize(path) > LOG_MAX_BYTES:
            os.replace(path, path + ".1")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{} {}\n".format(stamp, message))
    except OSError:
        pass


# --------------------------------------------------------------------------
# Notification building and sending
# --------------------------------------------------------------------------


def device_label(cfg):
    if cfg["device_name"]:
        return cfg["device_name"]
    try:
        return socket.gethostname() or ""
    except OSError:
        return ""


def build_notification(cfg, kind, project, duration_seconds, detail):
    """Return the ntfy JSON payload (without the topic)."""
    tag, priority = KINDS[kind]
    title = cfg.text(kind)
    if project:
        title = "{} · {}".format(title, project)

    detail = redact_secrets(detail)
    first_line = " · ".join(part for part in (
        format_duration(duration_seconds), device_label(cfg)) if part)
    lines = [line for line in (first_line, detail) if line]
    message = "\n".join(lines) or title

    return {"title": title, "message": message, "tags": [tag], "priority": priority}


def send(cfg, payload):
    body = dict(payload)
    body["topic"] = cfg["ntfy_topic"]
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "claude-toc/" + VERSION}
    if cfg["ntfy_token"]:
        headers["Authorization"] = "Bearer " + cfg["ntfy_token"]
    request = urllib.request.Request(cfg["ntfy_server"], data=data, headers=headers,
                                     method="POST")
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
        response.read()


# --------------------------------------------------------------------------
# Event handling
# --------------------------------------------------------------------------


def decide(cfg, event_name, event, enabled, now_dt, duration):
    """Return (kind, detail) to send, or (None, reason) to skip."""
    if not enabled:
        return None, "paused"

    now_minutes = now_dt.hour * 60 + now_dt.minute
    if in_quiet_hours(now_minutes, parse_hhmm(cfg["quiet_start"]), parse_hhmm(cfg["quiet_end"])):
        return None, "quiet hours"

    if event_name == "stop":
        text = event.get("last_assistant_message") or ""
        kind = "question" if is_question(text) else "finished"
        if cfg["min_duration_seconds"] > 0 and (
                duration is None or duration < cfg["min_duration_seconds"]):
            return None, "below minimum duration"
        detail = summarize_tail(text, cfg["summary_length"]) if cfg["include_summary"] else ""
        return kind, detail

    if event_name == "failure":
        errors = TEXTS[cfg.lang]["errors"]
        error = str(event.get("error") or "unknown")
        return "error", errors.get(error, errors["unknown"])

    if event_name == "notify":
        kind = "permission" if event.get("notification_type") == "permission_prompt" else "question"
        detail = strip_markdown(event.get("message") or "")
        return kind, detail[: cfg["summary_length"]]

    if event_name == "ask":
        detail = ""
        if cfg["include_summary"]:
            questions = (event.get("tool_input") or {}).get("questions") or []
            if questions and isinstance(questions[0], dict):
                detail = strip_markdown(questions[0].get("question") or "")
                detail = detail[: cfg["summary_length"]]
        return "question", detail

    return None, "unknown event"


def handle_hook(command, cfg, ddir, stdin_text):
    now = time.time()
    try:
        event = json.loads(stdin_text) if stdin_text.strip() else {}
        if not isinstance(event, dict):
            event = {}
    except ValueError:
        event = {}

    session_id = event.get("session_id")

    if command == "start":
        save_start(ddir, session_id, now, skip=is_own_command(event.get("prompt")))
        prune_starts(ddir, now)
        return

    start, skip = load_start(ddir, session_id)
    if skip and command == "stop":
        return  # the turn was one of our own /toc: commands
    duration = now - start if start is not None else None
    kind, detail = decide(cfg, command, event, is_enabled(ddir), datetime.now(), duration)
    if kind is None:
        return
    if not cfg["ntfy_topic"]:
        log(ddir, "no ntfy_topic configured; skipped {}".format(kind))
        return
    if not is_valid_topic(cfg["ntfy_topic"]):
        log(ddir, "invalid ntfy_topic (use letters, digits, - and _); skipped {}".format(kind))
        return

    project = find_project_name(event.get("cwd") or os.getcwd())
    send(cfg, build_notification(cfg, kind, project, duration, detail))


def handle_control(command, cfg, ddir):
    out = []
    if command == "on":
        set_enabled(ddir, True)
        out.append(cfg.text("on"))
    elif command == "off":
        set_enabled(ddir, False)
        out.append(cfg.text("off"))
    elif command == "test":
        if not cfg["ntfy_topic"]:
            out.append(cfg.text("no_topic"))
            return out, 1
        if not is_valid_topic(cfg["ntfy_topic"]):
            out.append(cfg.text("bad_topic"))
            return out, 1
        payload = build_notification(cfg, "test", find_project_name(os.getcwd()),
                                     None, cfg.text("test_message"))
        try:
            send(cfg, payload)
        except Exception as exc:  # report network errors to the user
            out.append(cfg.text("send_failed").format(error=exc))
            return out, 1
        out.append(cfg.text("sent").format(topic=mask_topic(cfg["ntfy_topic"])))
        out.extend(security_warnings(cfg))
    elif command == "status":
        out.extend(status_lines(cfg, ddir, datetime.now()))
    for warning in cfg.warnings:
        out.append("! " + warning)
    return out, 0


def status_lines(cfg, ddir, now_dt):
    t = TEXTS[cfg.lang]
    start, end = parse_hhmm(cfg["quiet_start"]), parse_hhmm(cfg["quiet_end"])
    quiet_on = start is not None and end is not None and start != end
    quiet_now = in_quiet_hours(now_dt.hour * 60 + now_dt.minute, start, end)
    if quiet_on:
        quiet = "{} - {}".format(cfg["quiet_start"], cfg["quiet_end"])
        if quiet_now:
            quiet += " (" + t["quiet_now"] + ")"
    else:
        quiet = t["quiet_disabled"]
    summary = (t["summary_on"].format(n=cfg["summary_length"])
               if cfg["include_summary"] else t["summary_off"])
    lines = [
        t["status_title"].format(version=VERSION),
        "- {}: {}".format(t["status_state"], t["state_on"] if is_enabled(ddir) else t["state_off"]),
        "- {}: {}".format(t["status_topic"], mask_topic(cfg["ntfy_topic"])),
        "- {}: {}".format(t["status_server"], cfg["ntfy_server"]),
        "- {}: {}".format(t["status_token"],
                          t["token_set"] if cfg["ntfy_token"] else t["token_unset"]),
        "- {}: {}".format(t["status_device"], device_label(cfg)),
        "- {}: {}".format(t["status_language"], cfg.lang),
        "- {}: {} s".format(t["status_min"], cfg["min_duration_seconds"]),
        "- {}: {}".format(t["status_quiet"], quiet),
        "- {}: {}".format(t["status_summary"], summary),
    ]
    warnings = security_warnings(cfg)
    if quiet_now:
        warnings.append(t["quiet_warning"])
    for warning in warnings:
        lines.append("")
        lines.append(warning)
    return lines


def security_warnings(cfg):
    out = []
    topic = cfg["ntfy_topic"]
    if topic and not is_valid_topic(topic):
        out.append(cfg.text("bad_topic"))
    elif topic and is_weak_topic(topic) and not cfg["ntfy_token"]:
        out.append(cfg.text("weak_topic"))
    if is_insecure_server(cfg["ntfy_server"]):
        out.append(cfg.text("insecure_server"))
    return out


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def parse_args(argv):
    """toc.py <command> [--data-dir DIR] [--set key=value ...]"""
    command, ddir, overrides = None, None, {}
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--data-dir" and index + 1 < len(argv):
            ddir = argv[index + 1]
            index += 2
            continue
        if arg == "--set" and index + 1 < len(argv):
            key, _, value = argv[index + 1].partition("=")
            overrides[key.strip()] = value
            index += 2
            continue
        if command is None:
            command = arg
        index += 1
    return command, ddir, overrides


def read_stdin():
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return ""
        return sys.stdin.buffer.read().decode("utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        return ""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    command, ddir_arg, overrides = parse_args(argv)

    if command in HOOK_COMMANDS:
        # Hooks never fail loudly and never print to stdout: stdout of a
        # UserPromptSubmit hook would be added to Claude's context.
        ddir = None
        try:
            ddir = data_dir(ddir_arg)
            snapshot_path = os.path.join(ddir, "config.json")
            raw = raw_options(overrides, os.environ, {})
            # Keep a copy of the hook's options for the control commands.
            if raw:
                write_json(snapshot_path, raw)
            cfg = build_config(raw_options(overrides, os.environ, read_json(snapshot_path, {})))
            for warning in cfg.warnings:
                log(ddir, "config: " + warning)
            handle_hook(command, cfg, ddir, read_stdin())
        except Exception as exc:
            if ddir:
                log(ddir, "{} failed: {!r}".format(command, exc))
        return 0

    if command in CONTROL_COMMANDS:
        ddir = data_dir(ddir_arg)
        snapshot = read_json(os.path.join(ddir, "config.json"), {})
        cfg = build_config(raw_options(overrides, os.environ, snapshot))
        lines, code = handle_control(command, cfg, ddir)
        # Always UTF-8: on Windows a piped stdout defaults to cp1252,
        # which garbles accents in the Bash tool's output.
        output = "\n".join(lines) + "\n"
        sys.stdout.flush()
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.flush()
        return code

    sys.stderr.write("usage: toc.py {" + ",".join(HOOK_COMMANDS + CONTROL_COMMANDS) + "}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
