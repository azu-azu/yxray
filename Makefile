.PHONY: dev build package

# Start both servers for local development.
# Terminal 1: Vite dev server on :5173 with HMR and /api proxy to FastAPI.
# Terminal 2: uvicorn on :7433 with --reload.
# NOTE: 'make dev' runs Vite in background and uvicorn in foreground.
#       Press Ctrl+C to stop uvicorn; kill the Vite process manually if needed.
dev:
	@echo "Starting FastAPI on :7433 and Vite on :5173..."
	@(cd app/frontend && npm run dev &) && uv run uvicorn app.server:app --port 7433 --reload

# Compile React frontend to app/frontend/dist/.
build:
	cd app/frontend && npm run build

# Full package: compile frontend, generate Windows VERSIONINFO, run PyInstaller.
# Requires: assets/icon.ico and version_info.yml to exist.
package: build
	uv run pyivf-make_version \
	  --source-format yaml \
	  --metadata-source version_info.yml \
	  --outfile file_version_info.txt \
	  --version $(shell uv run python -c "from importlib.metadata import version; print(version('alteryx-diff'))")
	uv run pyinstaller app.spec --noconfirm
