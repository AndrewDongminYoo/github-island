"""Build a deterministic Lambda ZIP containing only the package's Python source.

Usage: python tools/lambda_bundle.py OUTPUT.zip
"""

import sys
import zipfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "github_island"


def build(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(PACKAGE.glob("*.py")):
            entry = zipfile.ZipInfo("github_island/" + source.name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, source.read_bytes())
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(build(sys.argv[1]))
