#!/usr/bin/env bash
# Unified launcher for the MR Guardian image.
#
#   combined  (default)  Caddy on $PORT  ->  FastAPI (/api/*) + Streamlit (/)
#   api                  FastAPI only, on ${PORT:-8000}
#   dashboard            Streamlit only, on ${PORT:-8501}
#
# When started as root (e.g. Render mounts its persistent disk as root) the data
# directory is chowned and privileges are dropped to the non-root appuser via
# setpriv. When already non-root, it just runs the requested mode.
set -euo pipefail

DB_PATH="${MR_GUARDIAN_HISTORY_DB_PATH:-/data/history.sqlite}"
DATA_DIR="$(dirname "$DB_PATH")"
MODE="${1:-combined}"

# Internal ports for the combined mode (must match Caddyfile upstreams).
API_PORT=8800
DASH_PORT=8810

start_combined() {
	trap 'kill 0' SIGTERM SIGINT
	python -m uvicorn app.api:app --host 127.0.0.1 --port "$API_PORT" &
	python -m streamlit run app/streamlit_app.py \
		--server.port="$DASH_PORT" --server.address=127.0.0.1 \
		--server.headless=true --browser.gatherUsageStats=false \
		--server.enableCORS=false --server.enableXsrfProtection=false &
	caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
	wait -n
}

# Fix disk ownership and drop privileges when running as root.
if [ "$(id -u)" = "0" ]; then
	mkdir -p "$DATA_DIR"
	chown -R appuser:appuser "$DATA_DIR" 2>/dev/null || true
	exec setpriv --reuid appuser --regid appuser --init-groups -- "$0" "$@"
fi

case "$MODE" in
	combined)
		start_combined
		;;
	api)
		exec python -m uvicorn app.api:app --host 0.0.0.0 --port "${PORT:-8000}"
		;;
	dashboard)
		exec python -m streamlit run app/streamlit_app.py \
			--server.port="${PORT:-8501}" --server.address=0.0.0.0 \
			--server.headless=true --browser.gatherUsageStats=false
		;;
	*)
		exec "$@"
		;;
esac
