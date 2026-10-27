from __future__ import annotations

import os
from pathlib import Path

from mvp_runtime.app_paths import app_data_dir
from mvp_runtime.diagnostics import DiagnosticReport, Check, render_text


def test_app_data_override(tmp_path, monkeypatch):
    target = tmp_path / "state"
    monkeypatch.setenv("CAPCUT_TOOL_APPDATA", str(target))
    assert app_data_dir() == target
    assert target.is_dir()


def test_diagnostic_result_respects_required_checks():
    report = DiagnosticReport(
        app="x",
        version="1",
        python="3",
        platform="test",
        checks=[
            Check("required", "ok", "yes", required=True),
            Check("optional", "error", "missing", required=False),
        ],
    )
    assert report.ok is True
    assert "RESULT: READY" in render_text(report)


def test_diagnostic_fails_required_check():
    report = DiagnosticReport(
        app="x",
        version="1",
        python="3",
        platform="test",
        checks=[Check("required", "error", "missing", required=True)],
    )
    assert report.ok is False
    assert "RESULT: NOT READY" in render_text(report)
