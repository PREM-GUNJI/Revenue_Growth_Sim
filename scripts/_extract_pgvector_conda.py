"""One-shot helper: unpack conda-forge win-64 pgvector into TEMP for install."""
from __future__ import annotations

import io
import os
import tarfile
import zipfile
from pathlib import Path

dest = Path(os.environ["TEMP"]) / "pgvector-conda"
pkg = dest / "pgvector.conda"
out = dest / "files"
out.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(pkg) as zf:
    print("members:", zf.namelist())
    if "info/index.json" in zf.namelist():
        print(zf.read("info/index.json").decode())
    for name in zf.namelist():
        data = zf.read(name)
        if name.endswith(".tar.zst"):
            import zstandard as zstd

            tar_bytes = zstd.ZstdDecompressor().decompress(data, max_output_size=50_000_000)
            with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
                tar.extractall(out)
        elif name.endswith(".tar.bz2"):
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:bz2") as tar:
                tar.extractall(out)

for path in sorted(out.rglob("*")):
    if path.is_file() and (
        path.suffix.lower() in {".dll", ".control", ".sql"} or "vector" in path.name.lower()
    ):
        print(path)
