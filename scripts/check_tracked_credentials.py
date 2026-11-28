from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ALLOWED_ENV_FILES = {".env.example"}
BLOCKED_FILENAMES = {
    ".env",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
BLOCKED_SUFFIXES = {".jks", ".key", ".p12", ".pfx", ".pem", ".pkl", ".keystore"}
CONTENT_RULES = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:github_pat_|gh[opusr]_)[A-Za-z0-9_]{20,}\b"),
    "openai_project_key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    "credential_assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|password|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]"
    ),
}


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [Path(item) for item in result.stdout.decode().split("\0") if item]


def is_blocked_path(path: Path) -> bool:
    portable = PurePosixPath(path.as_posix())
    name = portable.name.lower()
    if name.startswith(".env") and name not in ALLOWED_ENV_FILES:
        return True
    return name in BLOCKED_FILENAMES or portable.suffix.lower() in BLOCKED_SUFFIXES


def scan_content(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return ["unreadable_tracked_file"]
    if len(raw) > 2_000_000 or b"\0" in raw:
        return []
    text = raw.decode("utf-8", errors="replace")
    findings: list[str] = []
    for line in text.splitlines():
        if any(marker in line.casefold() for marker in ("canary", "synthetic", "example")):
            continue
        findings.extend(name for name, pattern in CONTENT_RULES.items() if pattern.search(line))
    return sorted(set(findings))


def main() -> int:
    findings: list[tuple[str, str]] = []
    for path in tracked_paths():
        if not path.exists():
            continue
        if is_blocked_path(path):
            findings.append((path.as_posix(), "blocked_path"))
            continue
        findings.extend((path.as_posix(), rule) for rule in scan_content(path))
    if findings:
        for path, rule in findings:
            print(f"credential gate: {path}: {rule}", file=sys.stderr)
        return 1
    print("credential gate: no blocked tracked paths or credential patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
