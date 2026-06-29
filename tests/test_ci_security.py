"""Falsifiers for CI security gates and workflow wiring (st3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from warehouse.infra.security_gate import (
    pip_audit_blocking_findings,
    run_detect_secrets_gate,
    severity_from_cvss_vector,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = REPO_ROOT / ".secrets.baseline"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_secrets_baseline_exists() -> None:
    assert BASELINE.is_file(), (
        "commit .secrets.baseline for detect-secrets gate"
    )


def test_ci_workflow_has_st3_steps() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "warehouse test report" in text
    assert "upload-artifact" in text
    assert "runs/testing/coverage.json" in text
    assert "runs/testing/last_report.json" in text
    assert "security_gate pip-audit" in text
    assert "security_gate detect-secrets" in text


def test_severity_from_cvss_vector_high() -> None:
    vector = "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N"
    assert severity_from_cvss_vector(vector) == "HIGH"


def test_severity_from_cvss_vector_critical() -> None:
    vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert severity_from_cvss_vector(vector) == "CRITICAL"


def test_pip_audit_blocking_findings_filters_medium(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "dependencies": [
            {
                "name": "example",
                "version": "1.0.0",
                "vulns": [
                    {
                        "id": "CVE-TEST-MEDIUM",
                        "description": "test",
                    }
                ],
            }
        ]
    }

    def fake_osv(vuln_id: str) -> str:
        assert vuln_id == "CVE-TEST-MEDIUM"
        return "MEDIUM"

    monkeypatch.setattr(
        "warehouse.infra.security_gate.osv_severity",
        fake_osv,
    )
    assert pip_audit_blocking_findings(payload) == []


def test_pip_audit_blocking_findings_includes_high(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "dependencies": [
            {
                "name": "example",
                "version": "1.0.0",
                "vulns": [{"id": "CVE-TEST-HIGH"}],
            }
        ]
    }

    monkeypatch.setattr(
        "warehouse.infra.security_gate.osv_severity",
        lambda _vid: "HIGH",
    )
    findings = pip_audit_blocking_findings(payload)
    assert findings == [("example", "1.0.0", "CVE-TEST-HIGH", "HIGH")]


def test_pip_audit_gate_invocable() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "warehouse.infra.security_gate", "pip-audit"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in {0, 1}
    assert proc.stderr or proc.returncode == 0


def test_detect_secrets_gate_passes_when_scan_matches_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = tmp_path / ".secrets.baseline"
    finding = {
        "type": "AWSKeyDetector",
        "line_number": 1,
    }
    payload = {
        "version": "1.5.0",
        "results": {"leak.py": [finding]},
    }
    baseline.write_text(json.dumps(payload), encoding="utf-8")

    def fake_run(
        args: list[str],
        *,
        cwd: Path | None,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        _ = args, cwd, capture_output, text, check
        return subprocess.CompletedProcess(
            args=[sys.executable, "-m", "detect_secrets", "scan"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(
        "warehouse.infra.security_gate.subprocess.run",
        fake_run,
    )
    assert run_detect_secrets_gate(baseline_path=baseline, cwd=tmp_path) == 0


def test_detect_secrets_finds_planted_aws_key() -> None:
    planted = 'API_KEY = "AKIAIOSFODNN7EXAMPLE"'
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "detect_secrets",
            "scan",
            "--string",
            planted,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "AWSKeyDetector" in proc.stdout
    assert "True" in proc.stdout


def test_detect_secrets_gate_fails_on_new_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = tmp_path / ".secrets.baseline"
    baseline.write_text(
        json.dumps({"version": "1.5.0", "results": {}}),
        encoding="utf-8",
    )
    planted = tmp_path / "leak.py"
    planted.write_text(
        'TOKEN = "AKIAIOSFODNN7EXAMPLE"\n',
        encoding="utf-8",
    )

    scan_payload = json.dumps(
        {
            "version": "1.5.0",
            "results": {
                str(planted): [
                    {
                        "type": "AWSKeyDetector",
                        "line_number": 1,
                    }
                ]
            },
        }
    )

    def fake_run(
        args: list[str],
        *,
        cwd: Path | None,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        _ = args, cwd, capture_output, text, check
        return subprocess.CompletedProcess(
            args=[sys.executable, "-m", "detect_secrets", "scan"],
            returncode=0,
            stdout=scan_payload,
            stderr="",
        )

    monkeypatch.setattr(
        "warehouse.infra.security_gate.subprocess.run",
        fake_run,
    )
    exit_code = run_detect_secrets_gate(
        baseline_path=baseline,
        cwd=tmp_path,
    )
    assert exit_code == 1
