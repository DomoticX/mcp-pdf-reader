# bin/mutool

This directory holds the MuPDF CLI binary used by [`mcp-pdf-reader.py`](../mcp-pdf-reader.py). It is not committed to git (see [.gitignore](../.gitignore)) — provide it yourself.

## Windows

1. Go to the [mupdf-downloads releases](https://github.com/ArtifexSoftware/mupdf-downloads/releases) page.
2. Find the Windows build, e.g. `mupdf-1.28.0-windows.zip`.
3. Extract the archive and copy `mutool.exe` into this folder (`bin/mutool.exe`).

Verify:

```bash
bin\mutool.exe -v
```

## Linux

Either install the `mutool` package system-wide, which is simplest and is what the [Dockerfile](../Dockerfile) does:

```bash
sudo apt install mupdf-tools
```

...or download a Linux build from the [mupdf-downloads releases](https://github.com/ArtifexSoftware/mupdf-downloads/releases) page and place the `mutool` binary in this folder (`bin/mutool`, executable):

```bash
chmod +x bin/mutool
bin/mutool -v
```

The server checks `bin/` first and falls back to a `mutool` found on `PATH`, so either approach works without further configuration.

## If it's somewhere else

If [`config.json`](../config.json) should point at a custom location, set `mutool_path` there; otherwise the server auto-detects `bin/mutool.exe` / `bin/mutool` or a `mutool` on `PATH`.
