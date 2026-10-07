"""Verify the exact shipped application before hosted browser execution."""
from pathlib import Path
import hashlib,json,stat,zipfile
root=Path(__file__).resolve().parents[1];e=root/'evidence';e.mkdir(exist_ok=True)
expected={'index.html','web/core.js','web/worker-source.js','web/app.js','web/style.css','README-OFFLINE.txt'}
worker=(root/'web/core.js').read_text()+'\n'+(root/'web/worker.js').read_text()
assert (root/'web/worker-source.js').read_text()=='globalThis.OffDayWorkerSource='+json.dumps(worker,ensure_ascii=True)+';\n'
m=json.loads((root/'offline-manifest.json').read_text());assert set(m['files'])==expected
a=root/'off-day-kit-offline.zip';assert hashlib.sha256(a.read_bytes()).hexdigest()==m['zip_sha256']
with zipfile.ZipFile(a) as z:
    assert len(z.infolist())==6 and set(z.namelist())==expected and z.testzip() is None
    assert sum(i.file_size for i in z.infolist())<1_000_000
    for i in z.infolist():
        assert not stat.S_ISLNK(i.external_attr>>16)
        b=z.read(i.filename);assert b==(root/i.filename).read_bytes();assert hashlib.sha256(b).hexdigest()==m['files'][i.filename]
        p=e/'offline-app'/i.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
(e/'offline-package-result.json').write_text(json.dumps({'status':'pass',**m},indent=2)+'\n')
print('Exact shipped offline bytes verified')
