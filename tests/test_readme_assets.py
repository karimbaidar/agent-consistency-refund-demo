import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_image_references_exist():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    image_paths = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)

    assert image_paths
    assert all((ROOT / image_path).exists() for image_path in image_paths)
