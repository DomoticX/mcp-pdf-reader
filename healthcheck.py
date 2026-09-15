#!/usr/bin/env python3
"""
Docker HEALTHCHECK helper for the streamable-http transport.

Succeeds as soon as the MCP endpoint answers at all - even a 4xx (e.g. a
GET without a proper MCP session) proves the process is up and serving.
Only a connection failure counts as unhealthy. Stdlib-only.
"""

import sys
import urllib.error
import urllib.request

url = "http://127.0.0.1:8000/mcp"

try:
    urllib.request.urlopen(url, timeout=2)
except urllib.error.HTTPError:
    pass  # server answered - that's all "healthy" means here
except Exception:
    sys.exit(1)
