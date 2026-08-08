# bin/mutool.exe

This directory holds the MuPDF CLI binary (`mutool.exe`) used by [`mcp-pdf-reader.py`](../mcp-pdf-reader.py). It is not committed to git (see [.gitignore](../.gitignore)) — download it yourself:

1. Go to the [mupdf-downloads releases](https://github.com/ArtifexSoftware/mupdf-downloads/releases) page.
2. Find the Windows build, e.g. `mupdf-1.28.0-windows.zip`.
3. Extract the archive and copy `mutool.exe` into this folder (`bin/mutool.exe`).

## Verify

```bash
bin\mutool.exe -v
```

If [`config.json`](../config.json) points somewhere else, update `mutool_path` to match this file's actual location.
