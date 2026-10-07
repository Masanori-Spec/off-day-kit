"""Compare actual browser downloads with independent Python and literal oracles."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from off_day_kit.core import parse_project,Recipe,preview,apply
import date_oracle as literal
e=Path('evidence');source=(e/'gui-authored.gan').read_bytes();actual=(e/'generated.gan').read_bytes();report=json.loads((e/'generated-receipt.json').read_text())
project=parse_project(source);recipe=Recipe.from_dict(literal.RECIPE);plan=preview(project,recipe,['0','1']);expected=apply(project,plan)
assert actual==expected;assert report==plan.to_dict();literal.verify_raw(source,actual,report)
assert json.loads((e/'browser-recipe.json').read_text())==literal.RECIPE
assert (e/'browser-repeated.gan').read_bytes()==actual and (e/'browser-noop.gan').read_bytes()==actual
repeat=preview(parse_project(actual),recipe,['0','1']);assert json.loads((e/'browser-noop-receipt.json').read_text())==repeat.to_dict()
shifted=Recipe.from_dict(dict(literal.RECIPE,anchor='2027-01-11'));shifted_plan=preview(project,shifted,['0','1'])
assert (e/'browser-negative-shifted-anchor.gan').read_bytes()==apply(project,shifted_plan)
assert json.loads((e/'browser-negative-shifted-anchor-receipt.json').read_text())==shifted_plan.to_dict()
p=json.loads((e/'browser-production-result.json').read_text());assert p['status']=='pass' and p['sourceSha256']==hashlib.sha256(source).hexdigest()
for d in p['downloads']:assert hashlib.sha256((e/d['path']).read_bytes()).hexdigest()==d['sha256']
(e/'browser-oracle-result.json').write_text(json.dumps({'status':'pass','actualBrowserBytesEqualIndependentPython':True,'completeReceiptMatches':True,'actualRecipeMatches':True,'actualRepeatAndNoopMatch':True,'actualShiftedAnchorMatches':True,'sourceSha256':literal.sha(source),'outputSha256':literal.sha(actual)},indent=2)+'\n')
