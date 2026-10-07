#!/usr/bin/env bash
set -euo pipefail
export TZ=UTC LC_ALL=C.UTF-8
mkdir -p .native evidence
test ! -e .native/liberica-full.deb
curl --fail --location --connect-timeout 15 --max-time 180 --retry 1 \
  'https://github.com/bell-sw/Liberica/releases/download/21.0.12.1%2B1/bellsoft-jre21.0.12.1%2B1-linux-amd64-full.deb' \
  --output .native/liberica-full.deb
python3 - <<'PY'
from pathlib import Path, PurePosixPath
import hashlib,json,subprocess,tarfile
p=Path('.native/liberica-full.deb')
assert p.stat().st_size==79961672
digest=hashlib.sha256(p.read_bytes()).hexdigest()
assert digest=='b0adda900f561d67b3da3ff3c9d0cae4f84439e34cf4c8c049b6b0f6b60a10af'
process=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(p)],stdout=subprocess.PIPE)
files={};total=0;count=0
with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
    for member in archive:
        count+=1;total+=member.size
        assert count<=10000 and total<=1024*1024*1024
        path=PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        if member.isfile():
            source=archive.extractfile(member);h=hashlib.sha256()
            while chunk:=source.read(1024*1024): h.update(chunk)
            files['/'+str(path)]=h.hexdigest()
assert process.wait(timeout=10)==0
java_paths=[name for name in files if name.startswith('/usr/lib/jvm/') and name.endswith('/bin/java')]
assert len(java_paths)==1
runtime=str(PurePosixPath(java_paths[0]).parent.parent)
Path('.native/runtime-path.txt').write_text(runtime)
Path('evidence/runtime-release-integrity.json').write_text(json.dumps({'provider':'BellSoft Liberica Full JRE','version':'21.0.12.1+1','asset':517963967,'bytes':p.stat().st_size,'sha256':digest,'runtime':runtime,'javaPayloadSha256':files[java_paths[0]]},indent=2))
Path('.native/runtime-file-hashes.json').write_text(json.dumps({name:h for name,h in files.items() if name.startswith(runtime+'/')},indent=2))
PY
sudo apt-get install -y "$PWD/.native/liberica-full.deb"
python3 - <<'PY'
from pathlib import Path
import hashlib,json
files=json.loads(Path('.native/runtime-file-hashes.json').read_text())
assert files
for name,digest in files.items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
Path('evidence/installed-runtime-integrity.json').write_text(json.dumps({'allRegularPackageFilesMatch':True,'files':len(files)},indent=2))
PY
offday_runtime=$(cat .native/runtime-path.txt)
test ! -e .native/ganttproject.zip
curl --fail --location --connect-timeout 15 --max-time 180 --retry 1 \
  https://github.com/bardsoftware/ganttproject/releases/download/ganttproject-3.4.3396/ganttproject-3.4.3396.zip \
  --output .native/ganttproject.zip
python3 - <<'PY'
from pathlib import Path, PurePosixPath
import hashlib,json,stat,zipfile
p=Path('.native/ganttproject.zip')
assert p.stat().st_size==80256592
actual=hashlib.sha256(p.read_bytes()).hexdigest()
assert actual=='22ab7129525b25158a41f921ae92617a436b15bb3913a970acd6ec80edfd32e4'
Path('evidence/release-integrity.json').write_text(json.dumps({'tag':'ganttproject-3.4.3396','version':'3.4 Beta VI','commit':'36964e221d53cf52e72a3ab81722b15819be6253','asset':566731029,'bytes':p.stat().st_size,'sha256':actual},indent=2))
target=Path('.native/release')
assert not target.exists()
with zipfile.ZipFile(p) as z:
    members=z.infolist()
    assert len(members)<=10000 and len({i.filename for i in members})==len(members)
    assert sum(i.file_size for i in members)<=500*1024*1024
    for i in members:
        name=PurePosixPath(i.filename)
        assert not name.is_absolute() and '..' not in name.parts and '\\' not in i.filename and ':' not in i.filename
        kind=stat.S_IFMT(i.external_attr>>16)
        assert kind in (0,stat.S_IFREG,stat.S_IFDIR)
        assert i.file_size<=100*1024*1024 and not i.flag_bits & 1
    assert z.testzip() is None
    for i in members:
        dest=target/i.filename
        if i.is_dir():
            dest.mkdir(parents=True,exist_ok=True)
        else:
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:
                f.write(z.read(i))
    Path('evidence/release-members.json').write_text(json.dumps([{'path':i.filename,'bytes':i.file_size} for i in members],indent=2))
assert (target/'ganttproject').is_file() and (target/'eclipsito.jar').is_file()
PY
mkdir -p .native/probe-classes .native/probe-ipc
javac --release 17 -d .native/probe-classes native/UiProbe.java
printf 'Premain-Class: UiProbe\n\n' > .native/probe-manifest.txt
jar cfm .native/ui-probe.jar .native/probe-manifest.txt -C .native/probe-classes .
javac -version > evidence/compiler-version.txt 2>&1
"$offday_runtime/bin/java" -version > evidence/selected-runtime-version.txt 2>&1
"$offday_runtime/bin/java" --list-modules > evidence/selected-runtime-modules.txt
grep -q '^java.instrument@' evidence/selected-runtime-modules.txt
grep -q '^javafx.controls@' evidence/selected-runtime-modules.txt
grep -q '^javafx.swing@' evidence/selected-runtime-modules.txt
test -f "$offday_runtime/lib/libinstrument.so"
test -f "$offday_runtime/lib/libawt_xawt.so"
dpkg-query --show > evidence/installed-packages.txt
find .native/release -type f -print0 | sort -z | xargs -0 sha256sum > .native/vendor-before.sha256
find "$offday_runtime" -type f -print0 | sort -z | xargs -0 sha256sum >> .native/vendor-before.sha256
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
