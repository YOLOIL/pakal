"""PowerShell 7 + NuGet bootstrap for the Actions hub.

The script text lives in ``powershell_bootstrap.ps1``. This module fills the share path,
repository name and gallery URL, then wraps the result in a one-line ``pwsh -Command``.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from . import auth_config, config, nexus

_TEMPLATE = Path(__file__).resolve().parent / "powershell_bootstrap.ps1"
_PS_QUOTE = str.maketrans({"'": "''"})
# Used only when the admin console and Nexus have not set a gallery URL yet.
_FALLBACK_REPO_URL = "http://nexus.pituah.iaf/repository/powershell-hosted/"


def settings() -> Dict[str, Any]:
    return auth_config.load("powershell")


def repository_url(cfg: Dict[str, Any], nexus_cfg: Dict[str, Any]) -> str:
    explicit = str(cfg.get("repository_url") or "").strip()
    if explicit:
        return explicit if explicit.endswith("/") else explicit + "/"
    base = str(nexus_cfg.get("url") or "").rstrip("/")
    repos = nexus.repos_for(nexus_cfg, "powershell")
    if not base or not repos:
        return _FALLBACK_REPO_URL
    return f"{base}/repository/{quote(repos[0], safe='')}/"


def _ps_literal(value: str) -> str:
    return "'" + str(value).translate(_PS_QUOTE) + "'"


def build_script(nuget_path: str, repository_name: str, source: str) -> str:
    template = _TEMPLATE.read_text(encoding="utf-8")
    script = (
        template.replace("__NUGET_SOURCE__", _ps_literal(nuget_path))
        .replace("__REPO_NAME__", _ps_literal(repository_name))
        .replace("__REPO_URL__", _ps_literal(source))
    )
    return script.replace("\r\n", "\n").strip() + "\n"


def _command_body(script: str) -> str:
    """Collapse the bootstrap into one statement list that ``pwsh -Command`` can parse.

    ``param()`` stays attached to ``[CmdletBinding()]``. Every other line becomes its own
    statement. ``$`` is escaped later, for the double quotes of the outer paste.
    """
    lines = [line.strip() for line in script.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    folded = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("[CmdletBinding()]"):
            index += 1
            if index >= len(lines) or not lines[index].startswith("param"):
                folded.append("[CmdletBinding()]")
                continue
            chunk = []
            depth = 0
            while index < len(lines):
                part = lines[index]
                chunk.append(part)
                depth += part.count("(") - part.count(")")
                index += 1
                if depth <= 0 and any("(" in item for item in chunk):
                    break
            params = []
            for part in chunk:
                piece = part.strip().rstrip(",")
                if piece.startswith("param("):
                    piece = piece[len("param("):].strip().rstrip(",").rstrip(")")
                elif piece in {")", "param"}:
                    piece = ""
                if piece:
                    params.append(piece)
            folded.append("[CmdletBinding()] param(" + ", ".join(params) + ")")
            continue
        folded.append(line)
        index += 1
    return "; ".join(folded)


def build_command(script: str) -> str:
    """One line a standard user can paste into PowerShell 7. ``$`` is escaped for the outer quotes."""
    escaped = _command_body(script).replace("`", "``").replace('"', '`"').replace("$", "`$")
    return f'pwsh -NoProfile -ExecutionPolicy Bypass -Command "{escaped}"'


CMD_FILENAME = "Install-PAKAL-NuGet.cmd"
PS1_FILENAME = "Install-PAKAL-NuGet.ps1"
_DONE_MESSAGE = "ההתקנה הושלמה. nuget.exe הועתק ומאגר PowerShell נרשם עבור המשתמש."


def _values() -> Optional[tuple]:
    cfg = settings()
    source = repository_url(cfg, nexus.settings())
    nuget = str(cfg.get("nuget_exe_path") or "").strip() or config.DEFAULT_NUGET_EXE_PATH
    name = str(cfg.get("repository_name") or "").strip() or "NexusPS"
    if not nuget or not source:
        return None
    return cfg, nuget, name, source


def build_cmd_file() -> Optional[bytes]:
    """ASCII ``.cmd`` that runs the bootstrap in a hidden PowerShell 7 process.

    The script itself is UTF-16LE inside ``-EncodedCommand``, so Hebrew confirmation text
    survives ``cmd.exe`` code pages. A message box is the only thing the user sees.
    """
    values = _values()
    if values is None:
        return None
    _, nuget, name, source = values
    script = build_script(nuget, name, source).rstrip()
    done = _DONE_MESSAGE.replace("'", "''")
    # param() has to stay the first statement, so the failure dialog is a trap after it.
    trap = (
        "trap {\n"
        "  Add-Type -AssemblyName System.Windows.Forms\n"
        "  [System.Windows.Forms.MessageBox]::Show([string]$_.Exception.Message, 'PAKAL', 'OK', 'Error') | Out-Null\n"
        "  exit 1\n"
        "}\n"
    )
    marker = "$ErrorActionPreference = 'Stop'"
    if marker not in script:
        script = trap + script
    else:
        script = script.replace(marker, trap + marker, 1)
    runner = (
        script
        + "\nAdd-Type -AssemblyName System.Windows.Forms\n"
        + f"[System.Windows.Forms.MessageBox]::Show('{done}', 'PAKAL', 'OK', 'Information') | Out-Null\n"
    )
    encoded = base64.b64encode(runner.encode("utf-16-le")).decode("ascii")
    text = (
        "@echo off\r\n"
        "where pwsh >nul 2>&1\r\n"
        "if errorlevel 1 (\r\n"
        "  echo PowerShell 7 ^(pwsh^) is not installed.\r\n"
        "  echo Install it from the PAKAL software repository, then run this file again.\r\n"
        "  pause\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        "start \"\" pwsh -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand "
        + encoded
        + "\r\n"
        "exit /b 0\r\n"
    )
    return text.encode("ascii")


def build_ps1_file() -> Optional[bytes]:
    """Filled bootstrap script, without a ``-Scope`` argument on ``Register-PSRepository``."""
    values = _values()
    if values is None:
        return None
    _, nuget, name, source = values
    return build_script(nuget, name, source).encode("utf-8")


def public_setup() -> Dict[str, Any]:
    values = _values()
    cfg = settings()
    if values is None:
        nuget, name, source, ready = "", "", "", False
    else:
        _, nuget, name, source = values
        ready = True
    return {
        "configured": ready,
        "nuget_exe_path": nuget,
        "repository_name": name,
        "repository_url": source,
        "powershell7_url": str(cfg.get("powershell7_url") or "").strip(),
        "download_url": "/api/tools/setup-nuget.cmd" if ready else "",
        "download_name": CMD_FILENAME,
    }
