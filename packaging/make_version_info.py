"""Regenerate packaging/version_info.txt from measurelog.APP_VERSION."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = """# UTF-8
# Windows version resource for MeasureLog.
# Regenerate with: python packaging/make_version_info.py
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({quad}),
    prodvers=({quad}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('FileDescription', 'MeasureLog - replicate measurement logging'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'MeasureLog'),
         StringStruct('OriginalFilename', 'MeasureLog.exe'),
         StringStruct('ProductName', 'MeasureLog'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    source = (ROOT / "measurelog" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'APP_VERSION = "([^"]+)"', source).group(1)
    parts = [int(part) for part in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    target = ROOT / "packaging" / "version_info.txt"
    target.write_text(
        TEMPLATE.format(quad=", ".join(str(p) for p in parts[:4]), version=version),
        encoding="utf-8",
    )
    print(f"wrote {target} for version {version}")


if __name__ == "__main__":
    main()
