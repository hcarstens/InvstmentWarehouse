"""CI security gates — pip-audit (QA7) and detect-secrets baseline (st3)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_BLOCKING_SEVERITIES = frozenset({"HIGH", "CRITICAL"})
_CVSS_IMPACT = re.compile(r"CVSS:3\.[01]/.*")
_DEFAULT_BASELINE = Path(".secrets.baseline")
# Baseline JSON embeds hashed_secret hex digests that re-trigger detectors.
_EXCLUDE_FILES = r"\.secrets\.baseline$"
_OSV_URL = "https://api.osv.dev/v1/vulns/{vuln_id}"


def _secret_fingerprints(data: dict[str, Any]) -> set[tuple[str, str]]:
    """Stable (path, hashed_secret) keys — line numbers drift across edits."""
    keys: set[tuple[str, str]] = set()
    for path, findings in data.get("results", {}).items():
        if not isinstance(findings, list):
            continue
        for item in findings:
            if not isinstance(item, dict):
                continue
            digest = item.get("hashed_secret")
            if not isinstance(digest, str) or not digest:
                continue
            keys.add((str(path), digest))
    return keys


def severity_from_cvss_vector(vector: str) -> str:
    """Map a CVSS v3 vector string to a coarse severity band."""
    if not _CVSS_IMPACT.match(vector):
        return "UNKNOWN"
    parts = dict(
        segment.split(":", 1)
        for segment in vector.split("/")[1:]
        if ":" in segment
    )
    impacts = [parts.get(key, "N") for key in ("C", "I", "A")]
    high_count = sum(1 for value in impacts if value == "H")
    if high_count >= 3:
        return "CRITICAL"
    if high_count >= 1:
        return "HIGH"
    if any(value in {"L", "M"} for value in impacts):
        return "MEDIUM"
    return "LOW"


def osv_severity(vuln_id: str) -> str:
    """Return coarse severity for a vulnerability id via the OSV API."""
    url = _OSV_URL.format(vuln_id=vuln_id)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as err:
        raise RuntimeError(f"OSV lookup failed for {vuln_id}") from err

    severities = payload.get("severity")
    if isinstance(severities, list):
        for entry in severities:
            if not isinstance(entry, dict):
                continue
            score = entry.get("score")
            if isinstance(score, str) and score.startswith("CVSS"):
                return severity_from_cvss_vector(score)
    return "UNKNOWN"


def pip_audit_blocking_findings(
    audit_json: dict[str, Any],
) -> list[tuple[str, str, str, str]]:
    """Return (package, version, vuln_id, severity) for HIGH/CRITICAL vulns."""
    findings: list[tuple[str, str, str, str]] = []
    dependencies = audit_json.get("dependencies")
    if not isinstance(dependencies, list):
        return findings

    for dep in dependencies:
        if not isinstance(dep, dict):
            continue
        name = str(dep.get("name", ""))
        version = str(dep.get("version", ""))
        vulns = dep.get("vulns")
        if not isinstance(vulns, list):
            continue
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            vuln_id = str(vuln.get("id", ""))
            if not vuln_id:
                continue
            severity = osv_severity(vuln_id)
            if severity in _BLOCKING_SEVERITIES:
                findings.append((name, version, vuln_id, severity))
    return findings


def run_pip_audit_gate(
    *,
    python: str | None = None,
    cwd: Path | None = None,
) -> int:
    """Fail when installed deps have HIGH/CRITICAL known vulnerabilities."""
    executable = python or sys.executable
    proc = subprocess.run(
        [
            executable,
            "-m",
            "pip_audit",
            "-l",
            "--skip-editable",
            "-f",
            "json",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in {0, 1}:
        detail = proc.stderr.strip() or proc.stdout.strip()
        print(f"pip-audit failed: {detail}", file=sys.stderr)
        return proc.returncode or 1

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        print(f"pip-audit returned invalid JSON: {err}", file=sys.stderr)
        return 1

    blocking = pip_audit_blocking_findings(payload)
    if not blocking:
        return 0

    for name, version, vuln_id, severity in blocking:
        print(
            f"BLOCKING {severity}: {name} {version} — {vuln_id}",
            file=sys.stderr,
        )
    return 1


def run_detect_secrets_gate(
    *,
    baseline_path: Path | None = None,
    cwd: Path | None = None,
    python: str | None = None,
) -> int:
    """Fail when detect-secrets finds secrets not recorded in the baseline."""
    executable = python or sys.executable
    baseline = baseline_path or _DEFAULT_BASELINE
    if not baseline.is_file():
        print(f"detect-secrets baseline missing: {baseline}", file=sys.stderr)
        return 1

    try:
        baseline_data = json.loads(baseline.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"failed to read baseline {baseline}: {err}", file=sys.stderr)
        return 1

    proc = subprocess.run(
        [
            executable,
            "-m",
            "detect_secrets",
            "scan",
            "--exclude-files",
            _EXCLUDE_FILES,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        print(f"detect-secrets scan failed: {detail}", file=sys.stderr)
        return proc.returncode or 1

    try:
        current = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        print(f"detect-secrets returned invalid JSON: {err}", file=sys.stderr)
        return 1

    known = _secret_fingerprints(baseline_data)
    current_keys = _secret_fingerprints(current)
    new_keys = current_keys - known
    if not new_keys:
        return 0

    # Map digest → first finding for readable CI output.
    digest_meta: dict[tuple[str, str], tuple[str, int]] = {}
    for path, findings in current.get("results", {}).items():
        if not isinstance(findings, list):
            continue
        for item in findings:
            if not isinstance(item, dict):
                continue
            digest = item.get("hashed_secret")
            if not isinstance(digest, str) or not digest:
                continue
            key = (str(path), digest)
            if key in new_keys and key not in digest_meta:
                digest_meta[key] = (
                    str(item.get("type", "unknown")),
                    int(item.get("line_number", 0)),
                )

    for path, digest in sorted(new_keys):
        secret_type, line = digest_meta.get(
            (path, digest),
            ("unknown", 0),
        )
        print(
            f"NEW SECRET: {path}:{line} ({secret_type})",
            file=sys.stderr,
        )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CI security gates (QA7 st3)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("pip-audit", help="fail on HIGH/CRITICAL dependency vulns")
    secrets = sub.add_parser(
        "detect-secrets",
        help="fail when new secrets appear vs baseline",
    )
    secrets.add_argument(
        "--baseline",
        default=str(_DEFAULT_BASELINE),
        help="baseline JSON path (default: .secrets.baseline)",
    )

    args = parser.parse_args(argv)
    if args.command == "pip-audit":
        return run_pip_audit_gate()
    return run_detect_secrets_gate(baseline_path=Path(args.baseline))


if __name__ == "__main__":
    raise SystemExit(main())
