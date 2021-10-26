import json
import multiprocessing
import os

host = os.getenv("GUNICORN_HOST", "0.0.0.0")
port = os.getenv("GUNICORN_PORT", "8420")
bind_str = os.getenv("GUNICORN_BIND", f"{host}:{port}")
workers_config = os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1)
graceful_timeout_str = os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "120")
timeout_str = os.getenv("GUNICORN_TIMEOUT", "120")
keepalive_str = os.getenv("GUNICORN_KEEP_ALIVE", "5")

# Gunicorn config variables
bind = bind_str
workers = int(workers_config)
graceful_timeout = int(graceful_timeout_str)
timeout = int(timeout_str)
keepalive = int(keepalive_str)

log_data = {
    "workers": workers,
    "bind": bind,
    "graceful_timeout": graceful_timeout,
    "timeout": timeout,
    "keepalive": keepalive,
    "host": host,
    "port": port,
}
print(json.dumps(log_data, sort_keys=True, indent=4))
