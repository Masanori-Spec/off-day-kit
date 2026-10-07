"""Package exactly the original offline application source."""
from pathlib import Path
import hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
worker=(root/'web/core.js').read_text()+'\n'+(root/'web/worker.js').read_text()
(root/'web/worker-source.js').write_text('globalThis.OffDayWorkerSource='+json.dumps(worker,ensure_ascii=True)+';\n')
files=['index.html','web/core.js','web/worker-source.js','web/app.js','web/style.css','README-OFFLINE.txt']
with zipfile.ZipFile(root/'off-day-kit-offline.zip','w',zipfile.ZIP_STORED) as z:
    for name in files:
        info=zipfile.ZipInfo(name,(2026,10,7,0,0,0));info.external_attr=0o100644<<16
        z.writestr(info,(root/name).read_bytes())
(root/'offline-manifest.json').write_text(json.dumps({'files':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files},'zip_sha256':hashlib.sha256((root/'off-day-kit-offline.zip').read_bytes()).hexdigest()},indent=2)+'\n')
print('Built six-file offline source ZIP')
