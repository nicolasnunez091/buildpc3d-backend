import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fakeredis
import startup_check
import start_render


class StartupTests(unittest.TestCase):
    def test_script_isolated_and_concurrent(self):
        fake = fakeredis.FakeRedis()
        with contextlib.redirect_stdout(io.StringIO()) as logs:
            startup_check.check_redis(fake)
        self.assertIn("UPSTASH_CHECK TLS_PING OK", logs.getvalue())
        self.assertIn("UPSTASH_CHECK LUA_CONCURRENCIA_TTL OK", logs.getvalue())
        keys = [k.decode() for k in fake.keys("*")]
        self.assertTrue(keys)
        self.assertTrue(all(k.startswith("bpc:diagnostico:") for k in keys))
        self.assertTrue(all(0 < fake.ttl(k) <= 300 for k in keys))

    def test_failure_is_sanitized(self):
        with patch.dict(os.environ, {"REDIS_URL": "rediss://host"}, clear=True), \
             patch("startup_check.Redis.from_url", side_effect=RuntimeError("DO_NOT_PRINT")), \
             contextlib.redirect_stdout(io.StringIO()) as logs:
            self.assertFalse(startup_check.run())
        self.assertEqual(logs.getvalue().strip(), "UPSTASH_CHECK DIAGNOSTICO FALLO")

    def test_tls_certificate_validation_is_required(self):
        fake = fakeredis.FakeRedis()
        with patch.dict(os.environ, {"REDIS_URL": "rediss://example.invalid:6379"}, clear=True), \
             patch("startup_check.Redis.from_url", return_value=fake) as factory, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(startup_check.run())
        self.assertEqual(factory.call_args.kwargs["ssl_cert_reqs"], "required")
        self.assertTrue(factory.call_args.kwargs["ssl_check_hostname"])

    def test_diagnostic_refuses_enabled_groq(self):
        with patch.dict(os.environ, {"UPSTASH_STARTUP_CHECK": "true", "GROQ_ENABLED": "true"}, clear=True), \
             patch("start_render.os.execvp") as execute, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(start_render.main(), 1)
            execute.assert_not_called()

    def test_default_start_skips_diagnostic(self):
        with patch.dict(os.environ, {"PORT": "10000"}, clear=True), \
             patch("start_render.os.execvp", side_effect=RuntimeError("exec")) as execute, \
             patch("startup_check.run") as diagnostic:
            with self.assertRaises(RuntimeError):
                start_render.main()
            diagnostic.assert_not_called()
            self.assertIn("0.0.0.0:10000", execute.call_args.args[1])

    def test_invalid_flag_and_port_stop(self):
        for env in ({"UPSTASH_STARTUP_CHECK": "yes", "PORT": "10000"},
                    {"PORT": "not-a-port"}):
            with patch.dict(os.environ, env, clear=True), patch("start_render.os.execvp") as execute, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(start_render.main(), 1)
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
