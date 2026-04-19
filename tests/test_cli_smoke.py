import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_happy_path_smoke(tmp_path):
    env = {**os.environ, "OUTPUT_DIR": str(tmp_path), "MODEL_PROVIDER": "heuristic"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "refund_demo.cli",
            "--input",
            str(ROOT / "samples/inputs/happy_path.json"),
        ],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Workflow result: PASSED" in result.stdout
    assert "Receipts: 5" in result.stdout


def test_cli_failure_smoke(tmp_path):
    env = {**os.environ, "OUTPUT_DIR": str(tmp_path), "MODEL_PROVIDER": "heuristic"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "refund_demo.cli",
            "--input",
            str(ROOT / "samples/inputs/stale_policy.json"),
        ],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Workflow result: FAILED" in result.stdout
    assert "StaleStateError" in result.stdout
