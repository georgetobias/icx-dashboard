"""Verify that the release contains only code and the reproducible demo CSVs."""
from pathlib import Path
import re
import subprocess
import tempfile
from generate_demo import generate

ROOT = Path(__file__).resolve().parents[1]


def release_files():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode == 0 and result.stdout:
        return [ROOT / name for name in result.stdout.decode().split("\0") if name]
    ignored = {".git", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(part in ignored or part.startswith(".venv") for part in p.relative_to(ROOT).parts)]


def main():
    paths = release_files()
    allowed_suffixes = {".py", ".tsx", ".ts", ".css", ".json", ".md", ".yaml", ".html", ".spec"}
    for path in paths:
        rel = str(path.relative_to(ROOT))
        assert not path.is_symlink(), f"Symlink in release: {rel}"
        assert path.suffix in allowed_suffixes or rel in {".gitignore", ".env.example", "requirements.txt", "requirements-release.txt", "data/demo.csv", "data/schema.csv"}, f"Unexpected file type: {rel}"
        assert path.name != ".env", "Local environment file in release"
        text = path.read_text()
        assert not re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})", text), f"Credential pattern in {rel}"
        addresses = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        assert all(address.endswith("@example.invalid") for address in addresses), f"Non-demo address in {rel}"
    with tempfile.TemporaryDirectory(prefix="icx-release-check-") as tmp:
        generated = Path(tmp) / "demo.csv"
        generate(generated)
        for name in ["demo.csv", "schema.csv"]:
            assert (ROOT / "data" / name).read_bytes() == (Path(tmp) / name).read_bytes(), f"Demo was edited or replaced: {name}"
    print(f"Release checks passed: {len(paths)} files; demo CSVs reproduce exactly.")


if __name__ == "__main__":
    main()
