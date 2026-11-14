"""Tests for scripts/toc.py. Standard library only: python -m unittest"""

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "toc.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import toc  # noqa: E402


def cfg(**options):
    return toc.build_config(options)


class QuietHoursTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(toc.parse_hhmm("23:00"), 1380)
        self.assertEqual(toc.parse_hhmm("7:05"), 425)
        self.assertIsNone(toc.parse_hhmm("24:00"))
        self.assertIsNone(toc.parse_hhmm("abc"))

    def test_across_midnight(self):
        start, end = toc.parse_hhmm("23:00"), toc.parse_hhmm("07:00")
        self.assertTrue(toc.in_quiet_hours(23 * 60 + 30, start, end))
        self.assertTrue(toc.in_quiet_hours(3 * 60, start, end))
        self.assertFalse(toc.in_quiet_hours(7 * 60, start, end))
        self.assertFalse(toc.in_quiet_hours(12 * 60, start, end))

    def test_same_day(self):
        start, end = toc.parse_hhmm("12:00"), toc.parse_hhmm("13:00")
        self.assertTrue(toc.in_quiet_hours(12 * 60 + 30, start, end))
        self.assertFalse(toc.in_quiet_hours(13 * 60, start, end))

    def test_disabled_when_equal(self):
        value = toc.parse_hhmm("00:00")
        self.assertFalse(toc.in_quiet_hours(0, value, value))


class DurationTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(toc.format_duration(42), "42 s")
        self.assertEqual(toc.format_duration(272), "4 min 32 s")
        self.assertEqual(toc.format_duration(3900), "1 h 05 min")
        self.assertIsNone(toc.format_duration(None))


class QuestionTest(unittest.TestCase):
    def test_detects_question(self):
        self.assertTrue(toc.is_question("Feito. Quer que eu faça o deploy?"))
        self.assertTrue(toc.is_question("**Posso continuar?**\n\n"))
        self.assertFalse(toc.is_question("Pronto, os testes passaram."))
        self.assertFalse(toc.is_question(""))

    def test_question_followed_by_options(self):
        self.assertTrue(toc.is_question(
            "Posso seguir de dois jeitos.\n\nQual linguagem você prefere?\n\n"
            "- **Python**\n- **JavaScript**\n- Outra"))
        self.assertTrue(toc.is_question("Qual opção?\n1. Rápida\n2. Completa"))

    def test_question_followed_by_emoji_or_short_sentence(self):
        self.assertTrue(toc.is_question("Qual linguagem você prefere? 😊"))
        self.assertTrue(toc.is_question("Qual linguagem você prefere? Me conta!"))
        self.assertTrue(toc.is_question("Which one do you prefer?\n\n```\ncode\n```"))

    def test_real_claude_replies(self):
        self.assertTrue(toc.is_question(
            "Qual linguagem você prefere? Se for de programação, me diga qual "
            "(Python, Java...). Se for o idioma, me diga também (português...)."))
        self.assertTrue(toc.is_question(
            "Qual linguagem de programação você prefere?\n\n1. **Python**\n"
            "2. **JavaScript / TypeScript**\n3. **Java**\n\n"
            "Responda com o número ou o nome. Se preferir outra, é só dizer."))
        self.assertTrue(toc.is_question("Done. Let me know which approach you want."))

    def test_not_a_question(self):
        self.assertFalse(toc.is_question("Por que falhou? Porque faltava um import. Corrigi."))
        self.assertFalse(toc.is_question("Pronto, terminei.\n\n(Só para constar: não executei nada.)"))
        self.assertFalse(toc.is_question("Pronto. Criei:\n- ola.txt\n- README.md"))
        self.assertFalse(toc.is_question("Por que dá? Porque sim.\n\nTudo feito.\n\nArquivos salvos."))
        self.assertFalse(toc.is_question("Criei o arquivo ola.txt com o conteúdo oi."))


class SummaryTest(unittest.TestCase):
    def test_short_text_kept(self):
        self.assertEqual(toc.summarize_tail("Tudo certo.", 150), "Tudo certo.")

    def test_tail_starts_at_word(self):
        text = "palavra " * 40 + "fim da resposta."
        result = toc.summarize_tail(text, 30)
        self.assertTrue(result.startswith("…"))
        self.assertTrue(result.endswith("fim da resposta."))
        self.assertLessEqual(len(result), 31)
        self.assertFalse(result[1:].startswith(" "))

    def test_markdown_removed(self):
        text = "# Título\n\n- **item** com `código`\n- [link](http://x.y)\n\n```py\nx = 1\n```\nFim?"
        self.assertEqual(toc.strip_markdown(text), "Título item com código link Fim?")


class ProjectNameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_git_root_from_subfolder(self):
        repo = os.path.join(self.tmp, "padaria-app")
        sub = os.path.join(repo, "src", "api")
        os.makedirs(sub)
        os.makedirs(os.path.join(repo, ".git"))
        self.assertEqual(toc.find_project_name(sub), "padaria-app")

    def test_no_git(self):
        folder = os.path.join(self.tmp, "solta")
        os.makedirs(folder)
        self.assertEqual(toc.find_project_name(folder), "solta")


class ConfigTest(unittest.TestCase):
    def test_defaults(self):
        config = cfg()
        self.assertEqual(config.lang, "pt")
        self.assertEqual(config["quiet_start"], "23:00")
        self.assertTrue(config["include_summary"])

    def test_invalid_values_fall_back(self):
        config = cfg(language="fr", quiet_start="25:00", summary_length="abc",
                     min_duration_seconds="-3")
        self.assertEqual(config.lang, "pt")
        self.assertEqual(config["quiet_start"], "23:00")
        self.assertEqual(config["summary_length"], 150)
        self.assertEqual(config["min_duration_seconds"], 0)
        self.assertEqual(len(config.warnings), 4)

    def test_env_wins_over_overrides_and_snapshot(self):
        env = {"CLAUDE_PLUGIN_OPTION_LANGUAGE": "en"}
        raw = toc.raw_options({"language": "pt", "ntfy_topic": "a"}, env,
                              {"ntfy_topic": "b", "device_name": "PC"})
        self.assertEqual(raw, {"language": "en", "ntfy_topic": "a", "device_name": "PC"})

    def test_english_texts(self):
        self.assertEqual(cfg(language="en").text("finished"), "Finished")


class DecideTest(unittest.TestCase):
    noon = datetime(2026, 11, 14, 12, 0)
    night = datetime(2026, 11, 14, 23, 30)

    def test_finished(self):
        kind, detail = toc.decide(cfg(), "stop", {"last_assistant_message": "Feito."},
                                  True, self.noon, 10)
        self.assertEqual((kind, detail), ("finished", "Feito."))

    def test_question(self):
        kind, _ = toc.decide(cfg(), "stop", {"last_assistant_message": "Faço o deploy?"},
                             True, self.noon, 10)
        self.assertEqual(kind, "question")

    def test_paused_blocks_everything(self):
        for name in ("stop", "failure", "notify", "ask"):
            self.assertIsNone(toc.decide(cfg(), name, {}, False, self.noon, 10)[0])

    def test_quiet_hours_block_everything(self):
        event = {"notification_type": "permission_prompt", "error": "rate_limit"}
        for name in ("stop", "failure", "notify", "ask"):
            self.assertIsNone(toc.decide(cfg(), name, event, True, self.night, 10)[0])

    def test_minimum_duration(self):
        config = cfg(min_duration_seconds=60)
        event = {"last_assistant_message": "ok"}
        self.assertIsNone(toc.decide(config, "stop", event, True, self.noon, 59)[0])
        self.assertEqual(toc.decide(config, "stop", event, True, self.noon, 60)[0], "finished")
        self.assertIsNone(toc.decide(config, "stop", event, True, self.noon, None)[0])

    def test_permission_and_error_ignore_minimum(self):
        config = cfg(min_duration_seconds=600)
        kind, detail = toc.decide(config, "notify", {
            "notification_type": "permission_prompt",
            "message": "Claude needs your permission to use Bash"}, True, self.noon, 1)
        self.assertEqual(kind, "permission")
        self.assertIn("Bash", detail)
        kind, detail = toc.decide(config, "failure", {"error": "rate_limit"},
                                  True, self.noon, 1)
        self.assertEqual((kind, detail), ("error", "Limite de uso atingido"))

    def test_unknown_error_type(self):
        _, detail = toc.decide(cfg(language="en"), "failure", {"error": "new_thing"},
                               True, self.noon, 1)
        self.assertEqual(detail, "Unknown error")

    def test_ask_user_question(self):
        event = {"tool_input": {"questions": [{"question": "Qual banco de dados?"}]}}
        self.assertEqual(toc.decide(cfg(), "ask", event, True, self.noon, 5),
                         ("question", "Qual banco de dados?"))

    def test_summary_off(self):
        config = cfg(include_summary=False)
        self.assertEqual(toc.decide(config, "stop", {"last_assistant_message": "segredo"},
                                    True, self.noon, 5), ("finished", ""))


class SecurityTest(unittest.TestCase):
    def test_redacts_common_secrets(self):
        samples = [
            "token=abc123secret",
            'curl -H "Authorization: Bearer tk_AgQdq7mVBoFD37zQVN29RhuMzNIz2"',
            "chave sk-ant-api03-AAAAAAAAAAAAAAAAAAAA",
            "ghp_0123456789abcdefghij0123456789",
            "https://joao:minhasenha@github.com/x",
            'PASSWORD = "hunter22"',
            "AKIAABCDEFGHIJKLMNOP",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----",
        ]
        for sample in samples:
            redacted = toc.redact_secrets(sample)
            self.assertIn(toc.REDACTED, redacted, sample)
        for secret in ("abc123secret", "tk_AgQd", "sk-ant", "ghp_", "minhasenha",
                       "hunter22", "AKIA", "MIIE"):
            self.assertNotIn(secret, " ".join(toc.redact_secrets(x) for x in samples))

    def test_keeps_normal_text(self):
        text = "Corrigi o fluxo de password reset e contei os tokens do modelo."
        self.assertEqual(toc.redact_secrets(text), text)

    def test_notification_detail_is_redacted(self):
        payload = toc.build_notification(cfg(), "permission", "", None,
                                         "Rodar: export API_KEY=sk-123456789012345678901")
        self.assertNotIn("sk-1234", payload["message"])

    def test_topic_checks(self):
        self.assertFalse(toc.is_valid_topic("João"))
        self.assertFalse(toc.is_valid_topic("a b"))
        self.assertTrue(toc.is_valid_topic("toc-3f9a1c7e5b2d4f60"))
        self.assertTrue(toc.is_weak_topic("joao"))
        self.assertTrue(toc.is_weak_topic("meutopicosecreto"))
        self.assertFalse(toc.is_weak_topic("toc-3f9a1c7e5b2d4f60"))

    def test_insecure_server(self):
        self.assertTrue(toc.is_insecure_server("http://ntfy.example.com"))
        self.assertFalse(toc.is_insecure_server("https://ntfy.sh"))
        self.assertFalse(toc.is_insecure_server("http://127.0.0.1:8080"))

    def test_status_warns_about_weak_topic(self):
        lines = toc.status_lines(cfg(ntfy_topic="joao"), tempfile.mkdtemp(),
                                 datetime(2026, 11, 14, 12, 0))
        self.assertTrue(any("fácil de adivinhar" in line for line in lines))
        lines = toc.status_lines(cfg(ntfy_topic="joao", ntfy_token="tk_x"), tempfile.mkdtemp(),
                                 datetime(2026, 11, 14, 12, 0))
        self.assertFalse(any("fácil de adivinhar" in line for line in lines))

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    def test_private_files(self):
        folder = os.path.join(tempfile.mkdtemp(), "data")
        toc.data_dir(folder)
        toc.set_enabled(folder, True)
        self.assertEqual(os.stat(folder).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(os.path.join(folder, "state.json")).st_mode & 0o777, 0o600)


class NotificationTest(unittest.TestCase):
    def test_payload(self):
        payload = toc.build_notification(cfg(device_name="NOTEBOOK"), "finished",
                                         "padaria-app", 272, "Testes ok.")
        self.assertEqual(payload["title"], "Terminou · padaria-app")
        self.assertEqual(payload["message"], "4 min 32 s · NOTEBOOK\nTestes ok.")
        self.assertEqual(payload["tags"], ["white_check_mark"])
        self.assertEqual(payload["priority"], 3)

    def test_priorities(self):
        for kind in ("question", "permission", "error"):
            self.assertEqual(toc.build_notification(cfg(), kind, "", None, "")["priority"], 4)


class _Collector(http.server.BaseHTTPRequestHandler):
    received = []
    auth = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        _Collector.received.append(json.loads(self.rfile.read(length).decode("utf-8")))
        _Collector.auth.append(self.headers.get("Authorization"))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


class EndToEndTest(unittest.TestCase):
    """Runs toc.py as Claude Code would, against a local fake ntfy server."""

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Collector)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _Collector.received = []
        _Collector.auth = []
        self.data = tempfile.mkdtemp()
        self.project = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.project, ".git"))
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith("CLAUDE_PLUGIN_"):
                del self.env[key]
        self.env.update({
            "CLAUDE_PLUGIN_DATA": self.data,
            "CLAUDE_PLUGIN_OPTION_NTFY_TOPIC": "toc-test-topic-0123",
            "CLAUDE_PLUGIN_OPTION_NTFY_SERVER": "http://127.0.0.1:{}".format(
                self.server.server_address[1]),
            "CLAUDE_PLUGIN_OPTION_DEVICE_NAME": "PC",
            "CLAUDE_PLUGIN_OPTION_QUIET_START": "00:00",
            "CLAUDE_PLUGIN_OPTION_QUIET_END": "00:00",
        })

    def tearDown(self):
        shutil.rmtree(self.data, ignore_errors=True)
        shutil.rmtree(self.project, ignore_errors=True)

    def run_toc(self, *args, event=None, env=None):
        stdin = json.dumps(event or {}).encode("utf-8")
        return subprocess.run([sys.executable, SCRIPT] + list(args), input=stdin,
                              env=env or self.env, capture_output=True, timeout=30)

    def test_full_turn(self):
        event = {"session_id": "s1", "cwd": self.project}
        start = self.run_toc("start", event=dict(event, prompt="faz X"))
        self.assertEqual((start.returncode, start.stdout), (0, b""))
        stop = self.run_toc("stop", event=dict(
            event, last_assistant_message="Pronto. **Quer que eu faça o deploy?**"))
        self.assertEqual(stop.returncode, 0)
        self.assertEqual(len(_Collector.received), 1)
        sent = _Collector.received[0]
        self.assertEqual(sent["topic"], "toc-test-topic-0123")
        self.assertIsNone(_Collector.auth[0])
        self.assertEqual(sent["title"], "Pergunta · " + os.path.basename(self.project))
        self.assertEqual(sent["tags"], ["question"])
        self.assertTrue(sent["message"].startswith("0 s · PC\n") or
                        sent["message"].startswith("1 s · PC\n"))
        self.assertTrue(sent["message"].endswith("Quer que eu faça o deploy?"))

    def test_own_commands_do_not_notify(self):
        self.run_toc("start", event={"session_id": "s4", "prompt": "/toc:status"})
        self.run_toc("stop", event={"session_id": "s4", "last_assistant_message": "ok"})
        self.assertEqual(_Collector.received, [])
        self.run_toc("start", event={"session_id": "s4", "prompt": "corrige o /toc:x no README"})
        self.run_toc("stop", event={"session_id": "s4", "last_assistant_message": "ok"})
        self.assertEqual(len(_Collector.received), 1)

    def test_access_token_header(self):
        env = dict(self.env, CLAUDE_PLUGIN_OPTION_NTFY_TOKEN="tk_testtoken123")
        self.run_toc("stop", event={"session_id": "s5", "last_assistant_message": "ok"}, env=env)
        self.assertEqual(_Collector.auth, ["Bearer tk_testtoken123"])

    def test_invalid_topic_is_not_sent(self):
        env = dict(self.env, CLAUDE_PLUGIN_OPTION_NTFY_TOPIC="joão")
        self.run_toc("stop", event={"session_id": "s6", "last_assistant_message": "ok"}, env=env)
        self.assertEqual(_Collector.received, [])

    def test_hook_never_fails(self):
        env = dict(self.env, CLAUDE_PLUGIN_OPTION_NTFY_SERVER="http://127.0.0.1:9")
        result = self.run_toc("stop", event={"session_id": "s2"}, env=env)
        self.assertEqual((result.returncode, result.stdout), (0, b""))
        with open(os.path.join(self.data, "claude-toc.log"), encoding="utf-8") as handle:
            self.assertIn("stop failed", handle.read())
        bad = subprocess.run([sys.executable, SCRIPT, "stop"], input=b"not json{",
                             env=self.env, capture_output=True, timeout=30)
        self.assertEqual(bad.returncode, 0)

    def test_off_on_and_control_commands(self):
        control_env = {k: v for k, v in self.env.items()
                       if not k.startswith("CLAUDE_PLUGIN_OPTION_")}
        # The hook writes a config snapshot that the control commands reuse.
        self.run_toc("start", event={"session_id": "s3"})
        off = self.run_toc("off", "--data-dir", self.data, env=control_env)
        self.assertIn(b"/toc:on", off.stdout)
        self.run_toc("stop", event={"session_id": "s3", "last_assistant_message": "ok"})
        self.assertEqual(_Collector.received, [])
        test = self.run_toc("test", "--data-dir", self.data, env=control_env)
        self.assertEqual(test.returncode, 0, test.stdout)
        self.assertEqual(_Collector.received[0]["tags"], ["bell"])
        self.run_toc("on", "--data-dir", self.data, env=control_env)
        self.run_toc("stop", event={"session_id": "s3", "last_assistant_message": "ok"})
        self.assertEqual(len(_Collector.received), 2)
        status = self.run_toc("status", "--data-dir", self.data, "--set", "language=en",
                              env=control_env)
        self.assertIn("State: on", status.stdout.decode("utf-8"))
        self.assertIn("Topic: toc-…(19)", status.stdout.decode("utf-8"))

    def test_status_warns_in_quiet_hours(self):
        now = datetime.now()
        start = "{:02d}:00".format(now.hour)
        end = "{:02d}:00".format((now.hour + 1) % 24)
        control_env = {k: v for k, v in self.env.items()
                       if not k.startswith("CLAUDE_PLUGIN_OPTION_")}
        result = self.run_toc("status", "--data-dir", self.data,
                              "--set", "quiet_start=" + start, "--set", "quiet_end=" + end,
                              env=control_env)
        self.assertIn("ATIVO AGORA", result.stdout.decode("utf-8"))
        self.assertIn("não será avisado", result.stdout.decode("utf-8"))

    def test_old_start_files_pruned(self):
        folder = os.path.join(self.data, "starts")
        os.makedirs(folder)
        old = os.path.join(folder, "velha")
        open(old, "w").close()
        past = time.time() - 2 * 24 * 3600
        os.utime(old, (past, past))
        self.run_toc("start", event={"session_id": "nova"})
        self.assertEqual(os.listdir(folder), ["nova"])


if __name__ == "__main__":
    unittest.main()
