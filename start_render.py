"""Arranque propuesto para Render. No carga claves desde archivos."""
import os
import sys


def main():
    check = os.environ.get("UPSTASH_STARTUP_CHECK", "false").strip().lower()
    if check not in ("true", "false"):
        print("UPSTASH_CHECK CONFIG FALLO", flush=True)
        return 1
    if check == "true":
        if os.environ.get("GROQ_ENABLED", "false").strip().lower() != "false":
            print("UPSTASH_CHECK GROQ_DESACTIVADO FALLO", flush=True)
            return 1
        try:
            from startup_check import run
            # Un fallo se comunica; con Groq desactivado /health sigue disponible.
            run()
        except Exception:
            print("UPSTASH_CHECK DIAGNOSTICO FALLO", flush=True)
    port = os.environ.get("PORT", "")
    if not port.isdecimal() or not (1 <= int(port) <= 65535):
        print("UPSTASH_CHECK PORT FALLO", flush=True)
        return 1
    os.execvp("gunicorn", [
        "gunicorn", "--bind", "0.0.0.0:" + port, "--workers", "1",
        "--threads", "4", "--timeout", "30", "--access-logfile", "/dev/null",
        "--error-logfile", "-", "wsgi:app",
    ])
    return 1


if __name__ == "__main__":
    sys.exit(main())
