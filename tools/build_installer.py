#!/usr/bin/env python3
"""Build a deterministic, checksum-verified, self-contained user installer."""
import base64
import hashlib
import io
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from install import PACKAGE_FILES

HEADER='''#!/bin/bash
# Accented 0.1.0: user-only installer. Does not apply an accent.
set -euo pipefail
exec /usr/bin/python3 - "$0" "$@" <<'ACCENTED_BOOTSTRAP'
import base64, hashlib, io, os, pathlib, subprocess, sys, tempfile, zipfile
source=pathlib.Path(sys.argv[1]).read_bytes()
marker=b"\\n__ACCENTED_PAYLOAD__\\n"
payload=base64.b64decode(source.split(marker,1)[1],validate=False)
expected="@SHA@"
if hashlib.sha256(payload).hexdigest()!=expected:
    raise SystemExit("Installer checksum mismatch. Download the file again; nothing installed.")
with tempfile.TemporaryDirectory(prefix="accented-install-") as folder:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.infolist():
            name=pathlib.PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or entry.file_size>2000000:
                raise SystemExit("Unsafe archive entry. Nothing installed.")
            if ((entry.external_attr>>16)&0o170000)==0o120000:
                raise SystemExit("Symlink in archive. Nothing installed.")
        archive.extractall(folder)
    result=subprocess.run(["/usr/bin/python3",str(pathlib.Path(folder)/"install.py"),*sys.argv[2:]])
    raise SystemExit(result.returncode)
ACCENTED_BOOTSTRAP
__ACCENTED_PAYLOAD__
'''


def build(destination):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(PACKAGE_FILES):
            info=zipfile.ZipInfo(name,date_time=(2026,10,2,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,(ROOT/name).read_bytes())
    payload=output.getvalue()
    text=HEADER.replace('@SHA@',hashlib.sha256(payload).hexdigest())+base64.encodebytes(payload).decode()
    path=Path(destination);path.write_text(text);path.chmod(0o755)
    print(path,hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':build(sys.argv[1] if len(sys.argv)>1 else ROOT.parent/'Accented-0.1.0.run')
