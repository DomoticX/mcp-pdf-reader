#!/usr/bin/env python3
"""
mcp-pdf-reader.py
Minimal compatible MCP PDF reader using MuPDF's mutool CLI.

Cross-platform: works on Windows (bin/mutool.exe) and Linux (bin/mutool,
or a `mutool` already on PATH, e.g. installed via `apt install mupdf-tools`).

Flow:
1. Try native text extraction with MuPDF.
2. If extraction fails or yields too little useful text, render pages to PNG.
3. Return the PNG paths to the agent/model. This server does NOT perform OCR.

Requires:
    pip install mcp

Directory example:
    mcp-pdf-reader/
        mcp-pdf-reader.py
        config.json
        bin/
            mutool.exe   (Windows)  or  mutool  (Linux)

Transport:
    python mcp-pdf-reader.py --transport stdio                    (default)
    python mcp-pdf-reader.py --transport streamable-http --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import shutil
import time
from pathlib import Path
from typing import Any

# MCP SDK v2; keep a fallback for older v1 installations.
try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"

IS_WINDOWS = platform.system() == "Windows"
MUTOOL_BIN_NAME = "mutool.exe" if IS_WINDOWS else "mutool"

DEFAULT_CONFIG = {
    "mutool_path": str(BASE_DIR / "bin" / MUTOOL_BIN_NAME),
    "render_dpi": 300,
    "min_text_chars": 30,
    "render_output_dir": str(BASE_DIR / "temp"),
    "command_timeout_seconds": 300,
    "keep_rendered_pages": True,
    "cleanup_stale_after_seconds": 3600
}


def load_config() -> dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists():
        try:
            user_cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(user_cfg, dict):
                cfg.update(user_cfg)
        except Exception as exc:
            raise RuntimeError(f"Invalid config.json: {exc}") from exc

    return cfg


def resolve_mutool_path(cfg: dict[str, Any]) -> Path:
    """
    Resolve the mutool binary to use.

    Prefers the configured/default path (e.g. bin/mutool.exe or bin/mutool).
    Falls back to a `mutool` found on PATH, which covers Linux installs done
    via a package manager (e.g. `apt install mupdf-tools`) rather than the
    bin/ folder convention used on Windows.
    """
    configured = Path(cfg["mutool_path"]).expanduser()
    if configured.is_file():
        return configured

    on_path = shutil.which(MUTOOL_BIN_NAME) or shutil.which("mutool")
    if on_path:
        return Path(on_path)

    return configured


CONFIG = load_config()
MUTOOL = resolve_mutool_path(CONFIG)


def run_mutool(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run mutool without opening a console window on Windows."""
    if not MUTOOL.is_file():
        raise FileNotFoundError(
            f"mutool binary not found: {MUTOOL}. "
            f"Set 'mutool_path' in {CONFIG_FILE}, or make sure `{MUTOOL_BIN_NAME}` is on PATH."
        )

    timeout = timeout or int(CONFIG["command_timeout_seconds"])

    startupinfo = None
    creationflags = 0

    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    return subprocess.run(
        [str(MUTOOL), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        startupinfo=startupinfo,
        creationflags=creationflags,
        check=False,
    )


def validate_pdf_path(path: str) -> Path:
    p = Path(path).expanduser().resolve()

    if not p.exists():
        raise FileNotFoundError(f"PDF does not exist: {p}")
    if not p.is_file():
        raise ValueError(f"Path is not a file: {p}")
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file: {p}")

    return p


def useful_text_length(text: str) -> int:
    """
    Count useful, non-whitespace characters.
    This avoids treating a valid but image-only PDF as a successful text PDF.
    """
    return len(re.sub(r"\s+", "", text or ""))


def extract_native_text(pdf: Path) -> dict[str, Any]:
    proc = run_mutool(["draw", "-q", "-F", "txt", str(pdf)])

    text = proc.stdout or ""
    useful_chars = useful_text_length(text)

    return {
        "ok": proc.returncode == 0,
        "return_code": proc.returncode,
        "text": text,
        "useful_text_chars": useful_chars,
        "stderr": (proc.stderr or "").strip(),
    }


def make_render_dir(pdf: Path) -> Path:
    root = Path(CONFIG["render_output_dir"]).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    # Separate directory per PDF, sanitized to be a safe filename on any OS.
    safe_stem = re.sub(r'[^A-Za-z0-9._ -]+', "_", pdf.stem).strip(" .")
    safe_stem = safe_stem or "pdf"

    render_dir = root / safe_stem
    render_dir.mkdir(parents=True, exist_ok=True)
    return render_dir


def render_pages(pdf: Path, dpi: int | None = None) -> dict[str, Any]:
    dpi = int(dpi or CONFIG["render_dpi"])

    if dpi < 72 or dpi > 1200:
        raise ValueError("dpi must be between 72 and 1200")

    out_dir = make_render_dir(pdf)

    # Clear only PNGs generated by this tool for this PDF.
    for old_png in out_dir.glob("page-*.png"):
        try:
            old_png.unlink()
        except OSError:
            pass

    output_pattern = out_dir / "page-%03d.png"

    proc = run_mutool([
        "draw",
        "-q",
        "-r", str(dpi),
        "-F", "png",
        "-o", str(output_pattern),
        str(pdf),
    ])

    pages = sorted(out_dir.glob("page-*.png"))

    return {
        "ok": proc.returncode == 0 and bool(pages),
        "return_code": proc.returncode,
        "dpi": dpi,
        "pages": [str(p) for p in pages],
        "page_count": len(pages),
        "output_dir": str(out_dir),
        "stderr": (proc.stderr or "").strip(),
    }


def cleanup_render_dir_for_pdf(pdf: Path) -> dict[str, Any]:
    """Remove the temporary render directory for one PDF."""
    root = Path(CONFIG["render_output_dir"]).expanduser()
    safe_stem = re.sub(r'[^A-Za-z0-9._ -]+', "_", pdf.stem).strip(" .") or "pdf"
    render_dir = root / safe_stem

    existed = render_dir.exists()
    if existed:
        shutil.rmtree(render_dir, ignore_errors=True)

    return {
        "ok": True,
        "removed": existed,
        "output_dir": str(render_dir),
    }


def cleanup_stale_render_dirs() -> dict[str, Any]:
    """
    Remove stale rendered-PDF directories when keep_rendered_pages is false.

    This is a safety net for sessions that terminate before the agent calls
    cleanup_pdf(). Fresh render directories are left alone so Goose still has
    time to inspect returned PNG files.
    """
    if bool(CONFIG.get("keep_rendered_pages", True)):
        return {"ok": True, "enabled": False, "removed": []}

    root = Path(CONFIG["render_output_dir"]).expanduser()
    if not root.exists():
        return {"ok": True, "enabled": True, "removed": []}

    max_age = int(CONFIG.get("cleanup_stale_after_seconds", 3600))
    now = time.time()
    removed: list[str] = []

    for child in root.iterdir():
        if not child.is_dir():
            continue

        try:
            age = now - child.stat().st_mtime
            if age >= max_age:
                shutil.rmtree(child, ignore_errors=True)
                removed.append(str(child))
        except OSError:
            continue

    return {"ok": True, "enabled": True, "removed": removed}


mcp = MCPServer("Read Any PDF")


@mcp.tool()
def read_pdf(path: str, dpi: int | None = None) -> dict[str, Any]:
    """
    Read a PDF.

    First tries embedded/native text extraction with MuPDF.
    If that fails, or too little usable text is found, renders all pages
    to PNG and returns the image paths so the calling model can inspect/OCR them.

    Args:
        path: Absolute or relative path to the PDF.
        dpi: Optional PNG fallback DPI. Defaults to config.json.

    When keep_rendered_pages is false and image paths are returned, inspect
    all images first and then call cleanup_pdf(path) for this document.
    """
    pdf = validate_pdf_path(path)

    extraction = extract_native_text(pdf)
    min_chars = int(CONFIG["min_text_chars"])

    if extraction["ok"] and extraction["useful_text_chars"] >= min_chars:
        return {
            "ok": True,
            "mode": "text",
            "path": str(pdf),
            "text": extraction["text"],
            "useful_text_chars": extraction["useful_text_chars"],
            "message": "Usable embedded text found; no rendering required.",
        }

    rendered = render_pages(pdf, dpi=dpi)

    if not rendered["ok"]:
        return {
            "ok": False,
            "mode": "error",
            "path": str(pdf),
            "message": "Native text extraction was unusable and PNG rendering failed.",
            "text_extraction_error": extraction["stderr"],
            "render_error": rendered["stderr"],
            "return_code": rendered["return_code"],
        }

    reason = (
        f"Native text extraction returned only "
        f"{extraction['useful_text_chars']} useful characters "
        f"(minimum is {min_chars})."
        if extraction["ok"]
        else f"Native text extraction failed: {extraction['stderr'] or 'unknown error'}"
    )

    return {
        "ok": True,
        "mode": "images",
        "path": str(pdf),
        "reason": reason,
        "dpi": rendered["dpi"],
        "page_count": rendered["page_count"],
        "pages": rendered["pages"],
        "message": (
            "PDF pages were rendered to PNG. "
            "Inspect the returned images directly; this MCP server does not perform OCR. "
            + (
                "After all images have been inspected, call cleanup_pdf(path) to remove the temporary files."
                if not bool(CONFIG.get("keep_rendered_pages", True))
                else ""
            )
        ),
    }


@mcp.tool()
def extract_text(path: str) -> dict[str, Any]:
    """Force native text extraction only; never render pages."""
    pdf = validate_pdf_path(path)
    result = extract_native_text(pdf)

    return {
        "ok": result["ok"],
        "path": str(pdf),
        "text": result["text"],
        "useful_text_chars": result["useful_text_chars"],
        "stderr": result["stderr"],
        "return_code": result["return_code"],
    }


@mcp.tool()
def render_pdf(path: str, dpi: int | None = None) -> dict[str, Any]:
    """Force rendering of every PDF page to PNG."""
    pdf = validate_pdf_path(path)
    result = render_pages(pdf, dpi=dpi)

    return {
        "ok": result["ok"],
        "path": str(pdf),
        "dpi": result["dpi"],
        "page_count": result["page_count"],
        "pages": result["pages"],
        "output_dir": result["output_dir"],
        "stderr": result["stderr"],
        "return_code": result["return_code"],
    }


@mcp.tool()
def cleanup_pdf(path: str) -> dict[str, Any]:
    """
    Remove temporary PNG files created for this PDF.

    Call this only after all returned page images have been inspected.
    If keep_rendered_pages is true, cleanup is skipped.
    """
    pdf = validate_pdf_path(path)

    if bool(CONFIG.get("keep_rendered_pages", True)):
        return {
            "ok": True,
            "removed": False,
            "path": str(pdf),
            "message": "keep_rendered_pages is true; temporary files were kept.",
        }

    result = cleanup_render_dir_for_pdf(pdf)
    return {
        "ok": True,
        "removed": result["removed"],
        "path": str(pdf),
        "output_dir": result["output_dir"],
        "message": (
            "Temporary rendered pages removed."
            if result["removed"]
            else "No temporary render directory existed."
        ),
    }


@mcp.tool()
def cleanup_temp() -> dict[str, Any]:
    """
    Remove all temporary rendered PDF page directories.

    Use this for manual maintenance.
    If keep_rendered_pages is true, cleanup is skipped.
    """
    root = Path(CONFIG["render_output_dir"]).expanduser()

    if bool(CONFIG.get("keep_rendered_pages", True)):
        return {
            "ok": True,
            "removed": False,
            "output_dir": str(root),
            "message": "keep_rendered_pages is true; temporary files were kept.",
        }

    existed = root.exists()
    if existed:
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    return {
        "ok": True,
        "removed": existed,
        "output_dir": str(root),
        "message": "All temporary rendered PDF pages removed.",
    }


@mcp.tool()
def pdf_info(path: str) -> dict[str, Any]:
    """Return basic PDF information from MuPDF."""
    pdf = validate_pdf_path(path)

    # `mutool info` gives basic PDF metadata and page information.
    proc = run_mutool(["info", str(pdf)])

    return {
        "ok": proc.returncode == 0,
        "path": str(pdf),
        "info": proc.stdout,
        "stderr": (proc.stderr or "").strip(),
        "return_code": proc.returncode,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP PDF reader server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport protocol to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for streamable-http transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind for streamable-http transport (default: 8000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Remove leftovers from old sessions, but never fresh files the agent may still need.
    cleanup_stale_render_dirs()

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        # stdio is the normal transport when a client starts this script as a local extension.
        mcp.run(transport="stdio")
