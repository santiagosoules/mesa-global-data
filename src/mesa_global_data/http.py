from __future__ import annotations

import shutil
import subprocess
import tempfile
from email.message import Message
from email.parser import Parser
from pathlib import Path
from typing import Tuple


def _last_header_block(raw: str) -> Message:
    blocks = [block for block in raw.replace("\r\n", "\n").split("\n\n") if block.strip()]
    block = blocks[-1] if blocks else ""
    lines = block.splitlines()
    if lines and lines[0].startswith("HTTP/"):
        lines = lines[1:]
    return Parser().parsestr("\n".join(lines))


def fetch(url: str, timeout: int = 60, attempts: int = 3) -> Tuple[bytes, Message]:
    """Fetch a public source with curl for reliable proxy/TLS behavior on macOS.

    Arguments are passed as an argv list, never through a shell. Response headers and
    body are kept separate so source publication metadata cannot be confused with data.
    """
    executable = shutil.which("curl")
    if not executable:
        raise RuntimeError("curl is required for public-source retrieval")
    with tempfile.TemporaryDirectory(prefix="mesa-global-http-") as directory:
        header_path = Path(directory) / "headers.txt"
        body_path = Path(directory) / "body.bin"
        command = [
            executable, "--fail", "--location", "--silent", "--show-error",
            "--retry", str(max(attempts - 1, 0)), "--connect-timeout", "15",
            "--max-time", str(timeout),
            "--dump-header", str(header_path), "--output", str(body_path), url,
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            raise RuntimeError(
                "Failed to fetch {} with curl exit {}: {}".format(
                    url, result.returncode, result.stderr.decode("utf-8", errors="replace").strip()
                )
            )
        headers = _last_header_block(header_path.read_text(encoding="iso-8859-1"))
        return body_path.read_bytes(), headers

