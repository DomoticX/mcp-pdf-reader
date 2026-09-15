# mcp-pdf-reader — runs the MCP server over streamable-http for container use.
FROM python:3.12-slim

# mupdf-tools provides the `mutool` CLI (the Linux equivalent of bin/mutool.exe).
RUN apt-get update \
    && apt-get install -y --no-install-recommends mupdf-tools \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --no-create-home --shell /usr/sbin/nologin mcp

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-pdf-reader.py healthcheck.py config.json ./

# /data is where PDFs are expected to be mounted; /app/temp holds rendered pages.
RUN mkdir -p /app/temp /data && chown -R mcp:mcp /app /data

USER mcp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python healthcheck.py

ENTRYPOINT ["python", "mcp-pdf-reader.py"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
