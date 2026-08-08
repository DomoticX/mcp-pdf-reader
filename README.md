# mcp-pdf-reader

Minimal, dependency-light MCP server for reading PDFs, powered by MuPDF's `mutool.exe`.

## How it works

1. Tries native text extraction with MuPDF (`mutool draw -F txt`).
2. If extraction fails, or yields too little useful text (image-only / scanned PDFs), renders the pages to PNG instead.
3. Returns the PNG paths to the calling agent/model for inspection.

This server does **not** perform OCR itself — when a PDF needs it, the rendered page images are handed back for the model to read.

## Requirements

- Python 3.10+
- [`mcp`](https://pypi.org/project/mcp/) Python SDK:

  ```bash
  pip install mcp
  ```
- `mutool.exe` (MuPDF CLI) — see [bin/README.md](bin/README.md) for download instructions.

## Directory layout

```
mcp-pdf-reader/
├── mcp-pdf-reader.py   # server entry point
├── config.json         # runtime configuration
├── bin/
│   └── mutool.exe       # MuPDF CLI (not committed, see bin/README.md)
└── temp/                 # rendered page PNGs (created at runtime)
```

## Configuration

Settings are read from [config.json](config.json) at startup, falling back to built-in defaults for any key that's missing:

| Key | Default | Description |
| --- | --- | --- |
| `mutool_path` | `bin/mutool.exe` | Path to the MuPDF CLI binary |
| `render_dpi` | `300` | DPI used when rendering pages to PNG |
| `min_text_chars` | `30` | Minimum useful (non-whitespace) characters required to treat native extraction as successful |
| `render_output_dir` | `temp/` | Where rendered page PNGs are written |
| `command_timeout_seconds` | `300` | Timeout for each `mutool` invocation |
| `keep_rendered_pages` | `true` | If `false`, rendered PNGs are cleaned up via `cleanup_pdf` / on startup after `cleanup_stale_after_seconds` |
| `cleanup_stale_after_seconds` | `3600` | Age (seconds) after which stale render directories are removed on startup, when `keep_rendered_pages` is `false` |

**Note:** `mutool_path` and `render_output_dir` in `config.json` must point at paths that actually exist on your machine — update them if you move or rename this project folder.

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

The server communicates over stdio, the standard transport when started as an MCP extension (e.g. by Goose or Claude Desktop):

```bash
python mcp-pdf-reader.py
```
