# mcp-pdf-reader

Minimal, dependency-light MCP server for reading PDFs, powered by MuPDF's `mutool` CLI. Runs on Windows and Linux, either locally over stdio or as a local/network service over streamable-HTTP.

## How it works

1. Tries native text extraction with MuPDF (`mutool draw -F txt`).
2. If extraction fails, or yields too little useful text (image-only / scanned PDFs), renders the pages to PNG instead.
3. Returns the PNG paths to the calling agent/model for inspection.

This server does **not** perform OCR itself — when a PDF needs it, the rendered page images are handed back for the model to read.

## Requirements

- Python 3.10+
- [`mcp`](https://pypi.org/project/mcp/) Python SDK:

  ```bash
  pip install -r requirements.txt
  ```
- The `mutool` CLI (part of MuPDF):
  - **Windows:** place `mutool.exe` in `bin/` — see [bin/README.md](bin/README.md) for download instructions.
  - **Linux:** either place a `mutool` binary in `bin/`, or install it system-wide (e.g. `sudo apt install mupdf-tools`) so it's found on `PATH`.

## Directory layout

```
mcp-pdf-reader/
├── mcp-pdf-reader.py   # server entry point
├── config.json         # runtime configuration
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── healthcheck.py       # stdlib-only helper the container's HEALTHCHECK runs
├── bin/
│   └── mutool(.exe)     # MuPDF CLI (not committed, see bin/README.md)
└── temp/                 # rendered page PNGs (created at runtime)
```

## Configuration

Settings are read from [config.json](config.json) at startup, falling back to built-in defaults for any key that's missing:

| Key | Default | Description |
| --- | --- | --- |
| `mutool_path` | `bin/mutool.exe` (Windows) / `bin/mutool` (Linux) | Path to the MuPDF CLI binary. If it doesn't exist, a `mutool` found on `PATH` is used instead |
| `render_dpi` | `300` | DPI used when rendering pages to PNG |
| `min_text_chars` | `30` | Minimum useful (non-whitespace) characters required to treat native extraction as successful |
| `render_output_dir` | `temp/` | Where rendered page PNGs are written |
| `command_timeout_seconds` | `300` | Timeout for each `mutool` invocation |
| `keep_rendered_pages` | `true` | If `false`, rendered PNGs are cleaned up via `cleanup_pdf` / on startup after `cleanup_stale_after_seconds` |
| `cleanup_stale_after_seconds` | `3600` | Age (seconds) after which stale render directories are removed on startup, when `keep_rendered_pages` is `false` |

`mutool_path` and `render_output_dir` are resolved relative to the script's own folder by default, so the committed `config.json` normally only needs to override the settings above (e.g. `render_dpi`) — leave the paths out unless you have a nonstandard layout.

## MCP tools

| Tool | Description |
| --- | --- |
| `read_pdf(path, dpi=None)` | Extracts native text; falls back to rendering pages to PNG if too little usable text is found |
| `extract_text(path)` | Forces native text extraction only; never renders |
| `render_pdf(path, dpi=None)` | Forces rendering of every page to PNG |
| `cleanup_pdf(path)` | Removes temporary PNGs for a single PDF (only when `keep_rendered_pages` is `false`) |
| `cleanup_temp()` | Removes all temporary rendered PDF page directories |
| `pdf_info(path)` | Returns basic PDF metadata via `mutool info` |

## Running

The server supports two transports, selected with `--transport`:

```bash
# stdio (default) — for MCP clients that spawn the server themselves (Claude Desktop, Goose, ...)
python mcp-pdf-reader.py --transport stdio

# streamable-http — serves the MCP protocol over HTTP, for local network / containerized use
python mcp-pdf-reader.py --transport streamable-http --host 0.0.0.0 --port 8000
```

With `streamable-http`, the server listens on `http://<host>:<port>/mcp`.

## Docker

A `Dockerfile` and `docker-compose.yml` are included. The image installs `mutool` via `mupdf-tools` (apt) and always runs the server with `--transport streamable-http` (stdio isn't useful in a container, since there's no local process to pipe to). The container runs as a non-root user and ships a `HEALTHCHECK` that polls `/mcp` (any HTTP response, even a 4xx, counts as healthy — only a connection failure doesn't).

```bash
docker compose up --build
```

This starts the server on `http://localhost:8000/mcp`. Point your PDFs at the `./pdfs` folder next to `docker-compose.yml` (mounted read-only into the container as `/data`) and reference them from your MCP client as `/data/<file>.pdf`. Rendered pages persist in `./temp`.

To change the port, edit the `ports` mapping in `docker-compose.yml` (left side only — the container always listens on 8000 internally), or uncomment and edit the `command:` line to pass a different `--port`.
