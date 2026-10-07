#!/usr/bin/env bash
set -euo pipefail
export TZ=UTC LC_ALL=C.UTF-8
mkdir -p .native evidence
test ! -e .native/ganttproject.AppImage
curl --fail --location --connect-timeout 15 --max-time 180 --retry 1 \
  https://github.com/bardsoftware/ganttproject/releases/download/ganttproject-3.4.3396/ganttproject-3.4.3396.AppImage \
  --output .native/ganttproject.AppImage
python3 - <<'PY'
from pathlib import Path
import hashlib,json
p=Path('.native/ganttproject.AppImage')
assert p.stat().st_size==178039288
actual=hashlib.sha256(p.read_bytes()).hexdigest()
assert actual=='2147e92f25ea4c9efad30980b3e4d15def7ceeaec08c89ddf9b7eceb9fb0586c'
Path('evidence/release-integrity.json').write_text(json.dumps({'tag':'ganttproject-3.4.3396','version':'3.4 Beta VI','commit':'36964e221d53cf52e72a3ab81722b15819be6253','asset':566721059,'bytes':p.stat().st_size,'sha256':actual},indent=2))
PY
chmod u+x .native/ganttproject.AppImage
(cd .native && timeout --kill-after=5 60 ./ganttproject.AppImage --appimage-extract > ../evidence/appimage-extraction.log)
mkdir -p .native/probe-classes .native/probe-ipc
javac --release 17 -d .native/probe-classes native/UiProbe.java
printf 'Premain-Class: UiProbe\n\n' > .native/probe-manifest.txt
jar cfm .native/ui-probe.jar .native/probe-manifest.txt -C .native/probe-classes .
java -version > evidence/compiler-runtime.txt 2>&1
find .native/squashfs-root -type f -print0 | sort -z | xargs -0 sha256sum > .native/vendor-before.sha256
openbox > evidence/window-manager.log 2>&1 &
window_manager_pid=$!
trap 'kill "$window_manager_pid" 2>/dev/null || true' EXIT
timeout --kill-after=5 480 python3 scripts/gui_probe.py
sha256sum --check .native/vendor-before.sha256 > evidence/vendor-unchanged.txt
python3 - <<'PY'
from pathlib import Path
import json,hashlib
files={str(p.relative_to('evidence')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('evidence').rglob('*') if p.is_file()}
Path('evidence/file-hashes.json').write_text(json.dumps(files,indent=2,sort_keys=True))
PY
