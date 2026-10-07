import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto });
await import('../web/core.js');
const C = globalThis.OffDayCore;
const encode = value => new TextEncoder().encode(value);
const decode = value => new TextDecoder().decode(value);
const hash = value => createHash('sha256').update(value).digest('hex');
const root = fileURLToPath(new URL('../', import.meta.url));
const resource = (id = '0', name = 'Resource') => `<resource id="${id}" name="${name}"/>`;
const task = (id = '0', body = '') => `<task id="${id}" start="2027-01-01" duration="1">${body}</task>`;
const vacation = (id = '0', start = '2027-01-08', end = '2027-01-09') => `<vacation start="${start}" end="${end}" resourceid="${id}"/>`;
const projectText = ({ resources = resource(), tasks = '', vacations = '', extra = '', selfClosing = false } = {}) =>
  `<project name="Synthetic fixture" version="3.4.3396"><tasks>${tasks}</tasks><resources>${resources}</resources>${extra}${selfClosing ? '<vacations />' : `<vacations>${vacations}</vacations>`}</project>`;
const project = options => encode(projectText(options));
const recipeObject = (changes = {}) => ({ weekdays: ['friday'], every_weeks: 2, anchor: '2027-01-04', start: '2027-01-04', end: '2027-02-28', exclusions: ['2027-01-22'], ...changes });
const recipe = changes => C.parseRecipe(recipeObject(changes));
const ONE_DAY = recipe({ start: '2027-01-08', end: '2027-01-08', exclusions: [] });
const A = "<vacation resourceid='0'  end='2027-01-11' start='2027-01-08' />";
const B = '<vacation end="2027-02-02" resourceid="1" start="2027-02-01"></vacation>';
const SOURCE = encode('<?xml version="1.0" encoding="UTF-8"?>\r\n' +
  '<project name="Synthetic fixture" version="3.4.3396">\r\n' +
  '  <!-- Preserve this exact comment and all surrounding whitespace. -->\r\n' +
  '  <description><![CDATA[Literal <vacations/> & project notes]]></description>\r\n' +
  '  <tasks empty-milestones="true">\r\n' +
  '    <task id="10" name="Sentinel &amp; task" start="2027-01-05" duration="3" complete="17" expand="false">\r\n' +
  '      <notes><![CDATA[do not rewrite <vacation resourceid="9"/>]]></notes>\r\n' +
  '    </task>\r\n' +
  '    <task id="11" name="Dependent" start="2027-01-11" duration="1"><depend id="10" type="2"/></task>\r\n' +
  '  </tasks>\r\n' +
  '  <resources>\r\n' +
  '    <resource name="RESOURCEA" id="0"/>\r\n' +
  '    <resource id="1" name="RESOURCEB"/>\r\n' +
  '    <resource id="2" name="RESOURCEC 日本 &amp; &#67;"/>\r\n' +
  '  </resources>\r\n' +
  '  <allocations><allocation resource-id="0" task-id="10" load="100.0" responsible="true"/></allocations>\r\n' +
  `  <vacations>\r\n    ${A}\r\n    ${B}\r\n  </vacations>\r\n` +
  '  <roles roleset-name="Synthetic"><role id="0" name="Default"/></roles>\r\n' +
  '</project>\r\n<!-- trailing sentinel -->\r\n');
const rejects = input => assert.throws(() => C.parseProject(typeof input === 'string' ? encode(input) : input), C.OffDayKitError);
const interval = (id, start, end) => ({ resource_id: id, start, end_exclusive: end });

test('independent literal fixture: exact five additions, coverage, exclusions and complete receipt', async () => {
  const parsed = C.parseProject(SOURCE), plan = await C.preview(parsed, recipe(), ['1', '0']);
  assert.deepEqual(plan.additions, [interval('0', '2027-02-05', '2027-02-06'), interval('0', '2027-02-19', '2027-02-20'),
    interval('1', '2027-01-08', '2027-01-09'), interval('1', '2027-02-05', '2027-02-06'), interval('1', '2027-02-19', '2027-02-20')]);
  assert.equal(plan.addition_count, 5); assert.equal(plan.existing_interval_count, 2); assert.equal(plan.output_interval_count, 7);
  assert.deepEqual(plan.selected_resource_ids, ['0', '1']);
  assert.deepEqual(plan.candidate_dates, [
    { date: '2027-01-08', excluded: false }, { date: '2027-01-22', excluded: true },
    { date: '2027-02-05', excluded: false }, { date: '2027-02-19', excluded: false }
  ]);
  assert.deepEqual(plan.candidates_by_resource[0], {
    resource_id: '0', date: '2027-01-08', excluded: false, covered: true, status: 'covered',
    covering_interval_count: 1, covering_interval_example: interval('0', '2027-01-08', '2027-01-11')
  });
  assert.equal(plan.candidates_by_resource[1].status, 'excluded');
  assert.equal(plan.candidates_by_resource[4].status, 'add');
  assert.equal(plan.no_op, false);
  assert.equal(plan.source_sha256, hash(SOURCE));
  assert.equal(plan.output_sha256, hash(C.apply(parsed, plan)));
});

test('preserves every byte outside vacations, existing records, Unicode and literal fake markup', async () => {
  const parsed = C.parseProject(SOURCE), plan = await C.preview(parsed, recipe(), ['0', '1']);
  const output = C.apply(parsed, plan), original = decode(SOURCE), produced = decode(output);
  const before = original.indexOf('  <vacations>'), after = original.indexOf('</vacations>', before) + '</vacations>'.length;
  const newBefore = produced.indexOf('  <vacations>'), newAfter = produced.indexOf('</vacations>', newBefore) + '</vacations>'.length;
  assert.equal(produced.slice(0, newBefore), original.slice(0, before));
  assert.equal(produced.slice(newAfter), original.slice(after));
  assert.equal(produced.split(A).length - 1, 1); assert.equal(produced.split(B).length - 1, 1);
  assert.ok(produced.includes(`\r\n    ${A}\r\n    ${B}\r\n  `));
  assert.deepEqual(parsed.intervals.map(value => decode(value.raw)), [A, B]);
  assert.equal(C.parseProject(output).intervals.length, 7);
  assert.ok(C.parseProject(output).intervals.every(value => value.resource_id !== '2'));
  const inventory = await C.inventory(parsed);
  assert.equal(inventory.resources[2].name, 'RESOURCEC 日本 & C');
  assert.equal(inventory.existing_interval_count, 2);
});

test('second application and excluded coverage are byte-identical no-ops', async () => {
  const parsed = C.parseProject(SOURCE), first = C.apply(parsed, await C.preview(parsed, recipe(), ['0', '1']));
  const fresh = C.parseProject(first), repeat = await C.preview(fresh, recipe(), ['1', '0']);
  assert.equal(repeat.no_op, true); assert.deepEqual(repeat.additions, []); assert.deepEqual(C.apply(fresh, repeat), first);
  const excluded = await C.preview(parsed, recipe({ start: '2027-01-08', end: '2027-01-08', exclusions: ['2027-01-08'] }), ['0']);
  assert.equal(excluded.candidates_by_resource[0].excluded, true); assert.equal(excluded.candidates_by_resource[0].covered, true);
  assert.equal(excluded.candidates_by_resource[0].status, 'excluded'); assert.deepEqual(C.apply(parsed, excluded), SOURCE);
});

test('self-closing and paired empty sections expand identically to the literal byte recipe', async () => {
  for (const section of ['<vacations/>', '<vacations />', '<vacations\r\n\t/>', '<vacations></vacations>', '<vacations> </vacations>']) {
    const text = projectText().replace('<vacations></vacations>', section), parsed = C.parseProject(encode(text));
    const out = decode(C.apply(parsed, await C.preview(parsed, ONE_DAY, ['0'])));
    const records = '\n        <vacation start="2027-01-08" end="2027-01-09" resourceid="0"/>';
    const expectedSection = section.endsWith('/>') ? section.slice(0, -2) + '>' + records + '\n    </vacations>' : section.replace('</vacations>', records + '\n    </vacations>');
    assert.equal(out, text.replace(section, expectedSection));
  }
  const parsed = C.parseProject(project({ selfClosing: true }));
  const none = await C.preview(parsed, recipe({ start: '2027-01-04', end: '2027-01-04', exclusions: [] }), ['0']);
  assert.deepEqual(C.apply(parsed, none), parsed.source);
});

test('empty selection previews dates but cannot apply; selected resources sort numerically', async () => {
  const parsed = C.parseProject(project({ resources: resource('10') + resource('2') + resource('0') }));
  const a = await C.preview(parsed, recipe(), ['10', '0', '2']), b = await C.preview(parsed, recipe(), ['2', '10', '0']);
  assert.deepEqual(a, b); assert.deepEqual(a.selected_resource_ids, ['0', '2', '10']);
  const empty = await C.preview(parsed, recipe());
  assert.deepEqual(empty.candidates_by_resource, []); assert.equal(empty.candidate_dates.length, 4);
  assert.equal(empty.source_sha256, empty.output_sha256); assert.throws(() => C.apply(parsed, empty), C.OffDayKitError);
});

test('exclusive end is uncovered and all matching overlaps are counted without receipt amplification', async () => {
  const parsed = C.parseProject(project({ vacations: vacation('0', '2027-01-07', '2027-01-08') }));
  assert.equal((await C.preview(parsed, ONE_DAY, ['0'])).addition_count, 1);
  const overlaps = C.parseProject(project({ vacations: vacation().repeat(10000) }));
  const plan = await C.preview(overlaps, ONE_DAY, ['0']);
  assert.equal(plan.candidates_by_resource[0].covering_interval_count, 10000);
  assert.deepEqual(plan.candidates_by_resource[0].covering_interval_example, interval('0', '2027-01-08', '2027-01-09'));
  assert.ok(JSON.stringify(plan).length < 10000); assert.deepEqual(C.apply(overlaps, plan), overlaps.source);
  rejects(project({ vacations: vacation().repeat(10001) }));
});

test('fortnight parity before anchor, leap days, inclusive endpoints and finite planning range', async () => {
  const parsed = C.parseProject(project());
  const backwards = await C.preview(parsed, recipe({ anchor: '2027-02-01', start: '2027-01-01', end: '2027-02-14', exclusions: [] }));
  assert.deepEqual(backwards.candidate_dates.map(value => value.date), ['2027-01-08', '2027-01-22', '2027-02-05']);
  const leap = await C.preview(parsed, recipe({ weekdays: ['monday', 'tuesday'], every_weeks: 1, anchor: '2028-02-28', start: '2028-02-28', end: '2028-02-29', exclusions: [] }), ['0']);
  assert.deepEqual(leap.additions.map(value => value.start), ['2028-02-28', '2028-02-29']);
  recipe({ start: '2028-01-01', end: '2028-12-31', exclusions: [] });
  for (const [start, end] of [['1900-01-01', '1900-01-02'], ['2199-12-30', '2199-12-31']]) {
    const plan = await C.preview(parsed, recipe({ weekdays: ['monday'], every_weeks: 1, anchor: start, start, end: start, exclusions: [] }), ['0']);
    assert.equal(plan.additions[0].end_exclusive, end);
  }
});

test('recipe strict fields, types, duplicate selections/exclusions and modern range', () => {
  const changes = [
    { weekdays: [] }, { weekdays: ['Friday'] }, { weekdays: ['fri'] }, { weekdays: [4] }, { weekdays: 'friday' }, { weekdays: ['friday', 'friday'] },
    { weekdays: Array(1) }, { every_weeks: true }, { every_weeks: 0 }, { every_weeks: 3 }, { every_weeks: 1.5 }, { every_weeks: '2' },
    { anchor: '2027-01-05' }, { anchor: '0001-01-01' }, { anchor: '1899-12-25' }, { anchor: '2027-01-04T00:00:00' },
    { start: '2027-03-01' }, { start: '1582-10-10' }, { start: '1899-12-31' }, { start: '2027-1-04' },
    { end: '2028-01-05' }, { end: '2027-02-29' }, { end: '2200-01-01' },
    { anchor: '2199-12-30', start: '2199-12-31', end: '2199-12-31', exclusions: [] },
    { exclusions: '2027-01-22' }, { exclusions: null }, { exclusions: [1] }, { exclusions: ['2027-01-22', '2027-01-22'] },
    { exclusions: ['2027-03-01'] }, { exclusions: ['1582-10-10'] }, { exclusions: ['2027-01-22'].concat(Array(367)) }, { resource_ids: ['0'] }
  ];
  for (const change of changes) assert.throws(() => recipe(change), C.OffDayKitError, JSON.stringify(change));
  for (const input of [null, [], {}, { ...recipeObject(), exclusions: undefined }]) assert.throws(() => C.parseRecipe(input), C.OffDayKitError);
  const normalized = recipe({ weekdays: ['sunday', 'monday'], exclusions: ['2027-02-01', '2027-01-22'] });
  assert.deepEqual(normalized.weekdays, ['monday', 'sunday']); assert.deepEqual(normalized.exclusions, ['2027-01-22', '2027-02-01']);
  assert.deepEqual(C.parseRecipe(normalized), normalized);
});

test('JSON recipe rejects duplicate/escaped keys, floats, nonfinite values, invalid UTF-8 and size overflow', () => {
  const valid = JSON.stringify(recipeObject());
  assert.deepEqual(C.parseRecipe(encode(valid)), recipe());
  assert.deepEqual(C.parseRecipe(valid), recipe());
  const invalid = [
    new Uint8Array([255]), '{}x', valid.slice(0, -1) + ',"every_weeks":1}',
    valid.slice(0, -1) + ',"every_\\u0077eeks":1}',
    ...['NaN', 'Infinity', '-Infinity', '1.0', '1e0', '01', '1'.repeat(5000)].map(value => valid.replace('"every_weeks":2', `"every_weeks":${value}`)),
    ' '.repeat(65537), '\uFEFF' + valid, '{"weekdays":["friday",]}', '{"weekdays":[[[]]',
    valid.replace('"friday"', '"fri\nday"'), '['.repeat(70) + '0' + ']'.repeat(70)
  ];
  for (const input of invalid) assert.throws(() => C.parseRecipe(input), C.OffDayKitError);
  assert.deepEqual(C.parseRecipe(valid + ' '.repeat(65536 - encode(valid).length)), recipe());
});

test('terminal newlines never evade full-match validation of dates, IDs or numeric XML references', async () => {
  const parsed = C.parseProject(project());
  for (const suffix of ['\n', '\r', '\r\n', '\u2028', '\u2029']) {
    assert.throws(() => recipe({ anchor: '2027-01-04' + suffix }), C.OffDayKitError);
    await assert.rejects(C.preview(parsed, ONE_DAY, ['0' + suffix]), C.OffDayKitError);
  }
  rejects(project({ resources: resource('0&#10;') }));
  rejects(project({ tasks: task().replace('2027-01-01', '2027-01-01&#10;') }));
  rejects(project({ extra: '<calendars><date year="2027&#10;" month="01" date="01" type="1"/></calendars>' }));
  rejects(project({ resources: resource('0', '&#65\n;') }));
  rejects(project({ resources: resource('0', '&#x41\n;') }));
});

test('requires bytes, one well-formed project and exact sections/version/structure', () => {
  for (const input of [null, '<project/>', new ArrayBuffer(0)]) assert.throws(() => C.parseProject(input), C.OffDayKitError);
  const text = projectText();
  for (const input of ['', '<project>', text + text, '<other/>', text.replace('3.4.3396', '3.4.3397'), text.replace(' version="3.4.3396"', ''),
    projectText({ extra: '<unexpected/>' }), text.replace('<resources>', '<resources surprise="true">'), projectText({ resources: task() }),
    projectText({ tasks: resource() }), projectText({ vacations: resource() }), ...['<tasks/>', '<resources/>', '<vacations/>'].map(extra => projectText({ extra })),
    text.replace('<resources>', '<resources>unexpected text'), ...['<tasks></tasks>', '<resources>' + resource() + '</resources>', '<vacations></vacations>'].map(section => text.replace(section, ''))]) rejects(input);
});

test('IDs, durations, booleans, required attributes and references fail closed', () => {
  const invalid = ['00', '01', '-1', '+1', ' 1', '1 ', '1.0', '0x1', '2147483648', '١', ''];
  for (const value of invalid) { rejects(project({ resources: resource(value) })); rejects(project({ tasks: task(value) })); }
  assert.equal(C.parseProject(project({ resources: resource('2147483647') })).resources[0].id, '2147483647');
  for (const body of [resource('0') + resource('0', 'Other'), '<resource id="0"/>', '<resource name="Missing"/>']) rejects(project({ resources: body }));
  for (const body of [task('1') + task('1'), task('1', task('1')), '<task id="0" start="2027-01-01"/>', '<task id="0" duration="1"/>',
    ...['-1', '2147483648', '1.0', '1'.repeat(5000)].map(duration => `<task id="0" start="2027-01-01" duration="${duration}"/>`),
    task().replace('duration="1"', 'duration="1" meeting="1"'), task('0', '<depend id="9"/>')]) rejects(project({ tasks: body }));
  for (const extra of ['<allocations><allocation task-id="9" resource-id="0"/></allocations>', '<allocations><allocation task-id="0" resource-id="9"/></allocations>',
    '<allocations><allocation resource-id="0"/></allocations>']) rejects(project({ tasks: task(), extra }));
  rejects(project({ vacations: vacation('9') }));
  const forward = `<project version="3.4.3396"><vacations>${vacation()}</vacations><tasks>${task('1', '<depend id="2"/>')}${task('2')}</tasks>` +
    `<allocations><allocation task-id="2" resource-id="0"/></allocations><resources>${resource()}</resources></project>`;
  assert.equal(C.parseProject(encode(forward)).intervals.length, 1);
});

test('vacations require exact attributes, actual dates and strictly increasing endpoints', () => {
  const bad = ['2027-02-29', '2027-1-08', '0000-01-01', '2027-01-09T00:00:00'];
  for (const value of bad) { rejects(project({ vacations: vacation('0', value) })); rejects(project({ vacations: vacation('0', '2027-01-08', value) })); }
  for (const end of ['2027-01-08', '2027-01-07']) rejects(project({ vacations: vacation('0', '2027-01-08', end) }));
  for (const name of ['resourceid', 'start', 'end']) rejects(project({ vacations: vacation().replace(new RegExp(` ${name}="[^"]*"`), '') }));
});

test('every recognized XML date shares planning range, including defaults, custom values and baselines', () => {
  for (const value of ['0001-01-01', '1582-10-10', '1899-12-31', '2200-01-01', '2027-02-29']) {
    const [year, month, day] = value.split('-');
    const cases = [
      projectText({ vacations: vacation('0', value) }), projectText({ vacations: vacation('0', '2027-01-08', value) }),
      projectText().replace('<project ', `<project view-date="${value}" `), projectText({ tasks: task().replace('2027-01-01', value) }),
      projectText({ tasks: task().replace('id="0"', `id="0" thirdDate="${value}"`) }),
      projectText({ extra: `<previous><previous-tasks><previous-task id="0" start="${value}" duration="1"/></previous-tasks></previous>` }),
      projectText({ extra: `<calendars><date year="${year}" month="${Number(month)}" date="${Number(day)}" type="HOLIDAY"/></calendars>` }),
      projectText({ tasks: `<taskproperties><taskproperty id="x" valuetype="date" defaultvalue="${value}"/></taskproperties>` }),
      projectText({ tasks: `<taskproperties><taskproperty id="x" valuetype="date"/></taskproperties>${task('0', `<customproperty taskproperty-id="x" value="${value}"/>`)}` }),
      projectText({ resources: `<custom-property-definition id="x" type="date" default-value="${value}"/>${resource()}` }),
      projectText({ resources: `<custom-property-definition id="x" type="date"/><resource id="0" name="R"><custom-property definition-id="x" value="${value}"/></resource>` })
    ];
    for (const source of cases) rejects(source);
  }
  for (const value of ['1900-01-01', '2199-12-31']) C.parseProject(encode(projectText().replace('<project ', `<project view-date="${value}" `)));
  for (const year of ['', '*', '202']) rejects(project({ extra: `<calendars><date year="${year}" month="1" date="1" type="1"/></calendars>` }));
  for (const month of ['0', '13', '*']) rejects(project({ extra: `<calendars><date year="2027" month="${month}" date="1" type="1"/></calendars>` }));
});

test('custom property definitions are unique and required; unknown and legacy structures reject', () => {
  for (const tasks of ['<taskproperties><taskproperty id="x"/><taskproperty id="x"/></taskproperties>', task('0', '<customproperty taskproperty-id="missing" value="x"/>')]) rejects(project({ tasks }));
  for (const resources of ['<custom-property-definition id="x"/><custom-property-definition id="x"/>' + resource(),
    '<resource id="0" name="R"><custom-property definition-id="missing" value="x"/></resource>']) rejects(project({ resources }));
  for (const section of ['days', 'overriden-day-types']) rejects(project({ extra: `<calendars><day-types><${section}><date year="2027" month="1" date="1" type="1"/></${section}></day-types></calendars>` }));
});

test('rejects DTDs, entities, processing instructions, namespaces, BOMs, conflicting encodings and malformed XML', () => {
  const text = projectText();
  const sources = [
    '<!DOCTYPE project>' + text, '<!DOCTYPE project [<!ENTITY x "expansion">]>' + text,
    '<!DOCTYPE project SYSTEM "file:///etc/passwd">' + text, '<?target data?>' + text, projectText({ extra: '<?target data?>' }),
    text.replace('<project ', '<project xmlns="urn:test" '), text.replace('<project ', '<project xmlns:x="urn:test" '),
    text.replaceAll('resources>', 'x:resources>'), '\uFEFF' + text, '<?xml version="1.1"?>' + text,
    '<?xml version="1.0" encoding="ISO-8859-1"?>' + text, ' <?xml version="1.0"?>' + text,
    '<?xml encoding="UTF-8" version="1.0"?>' + text, '<?XML version="1.0"?>' + text,
    projectText({ resources: resource('0', '&custom;') }), projectText({ resources: resource('0', '&#0;') }),
    projectText({ resources: resource('0', '&#xD800;') }), projectText({ resources: resource('0', '&#1114112;') }),
    projectText({ resources: resource('0', '&#xFFFE;') }), projectText({ resources: resource('0', '<literal>') }),
    projectText({ resources: resource('0', 'bad\u0001') }), projectText({ resources: resource('0', '&unfinished') }),
    text.replace('<resource id=', '<resource id="1" id='), text.replace('id="0" name=', 'id="0"name='),
    text.replace('</tasks>', '</resources>'), text.replace('<tasks>', '<tasks/ >'), text.replace('<tasks>', '<tasks / >'),
    projectText({ extra: '<!-- bad -- middle -->' }), projectText({ extra: '<!-- bad --->' }),
    projectText({ extra: '<description>]]></description>' }), '&#32;' + text, text + '&#32;'
  ];
  for (const source of sources) rejects(source);
  for (const prefix of [[255, 254], [254, 255], [192, 175], [237, 160, 128]]) rejects(new Uint8Array([...prefix, ...project()]));
  for (const declaration of ['<?xml version="1.0"?>', "<?xml version='1.0' encoding='utf-8' standalone='yes'?>", '<?xml version="1.0" standalone="no"?>']) C.parseProject(encode(declaration + text));
});

test('oversized XML names and other attacker-controlled diagnostics remain bounded', () => {
  const hugeName = 'x'.repeat(1000000);
  for (const source of [projectText({ extra: `<${hugeName}/>` }), projectText().replace('<tasks>', `<tasks ${hugeName}="">`),
    projectText().replace('</tasks>', `</${hugeName}>`)]) {
    assert.throws(() => C.parseProject(encode(source)), error => {
      assert.ok(error instanceof C.OffDayKitError);
      assert.equal(error.message, 'XML name length limit exceeded');
      return true;
    });
  }
  const longDefinition = '日'.repeat(4000);
  const source = project({ tasks: task('0', `<customproperty taskproperty-id="${longDefinition}"/>`) });
  assert.throws(() => C.parseProject(source), error => {
    assert.ok(error instanceof C.OffDayKitError); assert.ok(error.message.length <= 512); return true;
  });
  const key = 'x'.repeat(10000);
  assert.throws(() => C.parseRecipe(`{"${key}":0,"${key}":1}`), error => {
    assert.ok(error instanceof C.OffDayKitError); assert.ok(error.message.length <= 512); return true;
  });
  assert.equal(new C.OffDayKitError('x'.repeat(1000000)).message.length, 512);
});

test('standard/numeric entities, CRLF normalization, comments and CDATA are accepted without byte rewriting', async () => {
  const source = project({ resources: resource('0', "A\r\nB\tC&#10;D&#13;E &amp; &lt; &gt; &apos; &quot; &#x1F600;"),
    tasks: task('0', '<notes><![CDATA[a < b && c > d\r\n日本]]></notes>'),
    extra: '<!-- outside vacations --><description><![CDATA[<vacations/>]]></description>' });
  const parsed = C.parseProject(source);
  assert.equal(parsed.resources[0].name, 'A B C\nD\rE & < > \' " 😀');
  const plan = await C.preview(parsed, recipe({ start: '2027-01-04', end: '2027-01-04', exclusions: [] }), ['0']);
  assert.deepEqual(C.apply(parsed, plan), source);
  for (const vacations of ['<!-- ambiguous -->', '<![CDATA[ ]]>', vacation().replace('/>', '><!-- ambiguous --></vacation>')]) rejects(project({ vacations }));
});

test('untrusted links, expressions and markup stay inert', async () => {
  const source = project({ tasks: task('0', '<notes>&lt;script&gt;alert(1)&lt;/script&gt;</notes>').replace('duration="1"', 'duration="1" webLink="file:///private/not-read"'),
    extra: '<view><option value="javascript:alert(1)"/><filters><filter><simple-select select="fetch(\'https://invalid.example\')" where="anything"/></filter></filters></view>' });
  const parsed = C.parseProject(source), output = C.apply(parsed, await C.preview(parsed, ONE_DAY, ['0']));
  assert.ok(decode(output).includes('file:///private/not-read')); assert.ok(decode(output).includes('javascript:alert(1)'));
});

test('source buffers, interval copies and receipts cannot be mutated to change an applied plan', async () => {
  const input = project({ vacations: vacation() }), original = input.slice(), parsed = C.parseProject(input);
  input.fill(0); parsed.source.fill(0); parsed.intervals[0].raw.fill(0);
  assert.deepEqual(parsed.source, original);
  const plan = await C.preview(parsed, ONE_DAY, ['0']);
  assert.throws(() => { plan.no_op = false; }, TypeError);
  assert.throws(() => { plan.selected_resource_ids.push('1'); }, TypeError);
  assert.throws(() => { plan.recipe.weekdays[0] = 'monday'; }, TypeError);
  assert.throws(() => { plan.candidates_by_resource[0].covered = false; }, TypeError);
  for (const altered of [{ ...plan, additions: [] }, { ...plan, output_sha256: '0'.repeat(64) }, JSON.parse(JSON.stringify(plan))]) assert.throws(() => C.apply(parsed, altered), C.OffDayKitError);
  const output = C.apply(parsed, plan); output.fill(0); assert.deepEqual(C.apply(parsed, plan), original);
  assert.deepEqual(C.apply(C.parseProject(original), plan), original);
  assert.throws(() => C.apply(C.parseProject(encode(decode(original).replace('<tasks>', '<tasks> '))), plan), C.OffDayKitError);
  assert.throws(() => C.apply({ source: original }, plan), C.OffDayKitError);
});

test('selected resource cap and validation; generated intervals share 10000 total', async () => {
  const parsed = C.parseProject(project({ resources: Array.from({ length: 101 }, (_, i) => resource(String(i))).join('') }));
  const selected = Array.from({ length: 100 }, (_, i) => String(i));
  assert.equal((await C.preview(parsed, ONE_DAY, selected)).addition_count, 100);
  for (const selection of [[...selected, '100'], ['999'], ['0', '0'], ['00'], [0], [true], ['-1'], ['2147483648'], '0', null]) await assert.rejects(C.preview(parsed, ONE_DAY, selection), C.OffDayKitError);
  const almost = C.parseProject(project({ vacations: vacation('0', '2027-01-01', '2027-01-02').repeat(9999) }));
  const plan = await C.preview(almost, ONE_DAY, ['0']); assert.equal(C.parseProject(C.apply(almost, plan)).intervals.length, 10000);
  await assert.rejects(C.preview(almost, recipe({ start: '2027-01-08', end: '2027-01-22', exclusions: [] }), ['0']), C.OffDayKitError);
});

test('actual depth, element and per-element attribute bounds', () => {
  function nested(count) { let body = ''; for (let i = 0; i < count; i++) body = task(String(i), body); return project({ tasks: body }); }
  C.parseProject(nested(30)); rejects(nested(31));
  C.parseProject(project({ extra: '<roles>' + '<role/>'.repeat(49994) + '</roles>' }));
  rejects(project({ extra: '<roles>' + '<role/>'.repeat(49995) + '</roles>' }));
  // The profile exposes fewer than 32 legal attributes per tag; arbitrary attrs
  // still must fail, even if the count limit is reached before the allowlist.
  rejects(projectText().replace('<tasks>', '<tasks ' + Array.from({ length: 33 }, (_, i) => `x${i}=""`).join(' ') + '>'));
});

function attributeCountBoundary() {
  const body = Array.from({ length: 22221 }, (_, i) => `<task id="${i}" start="2027-01-01" duration="1" name="" color="" shape="" complete="0" priority="0" uid=""/>`).join('');
  return projectText({ tasks: body + '<task id="22221" start="2027-01-01" duration="1" name="" color="" shape="" complete="0"/>' });
}
test('actual total attribute count and decoded individual/aggregate attribute byte bounds', () => {
  const text = attributeCountBoundary(); C.parseProject(encode(text)); rejects(text.replace('id="22221"', 'id="22221" uid="extra"'));
  C.parseProject(project({ resources: resource('0', 'A'.repeat(16384 - 4)) }));
  rejects(project({ resources: resource('0', 'A'.repeat(16384 - 3)) })); rejects(project({ resources: resource('0', '日'.repeat(5461)) }));
  rejects(project({ resources: Array.from({ length: 263 }, (_, i) => resource(String(i), 'A'.repeat(16000))).join('') }));
});

test('actual node/aggregate decoded text and comment byte bounds', () => {
  const limit = 256 * 1024;
  C.parseProject(project({ extra: '<description>' + 'A'.repeat(limit) + '</description>' }));
  rejects(project({ extra: '<description>' + 'A'.repeat(limit + 1) + '</description>' }));
  const notes = '<notes>' + 'A'.repeat(limit) + '</notes>';
  C.parseProject(project({ tasks: Array.from({ length: 8 }, (_, i) => task(String(i), notes)).join('') }));
  rejects(project({ tasks: Array.from({ length: 9 }, (_, i) => task(String(i), notes)).join('') }));
  C.parseProject(project({ extra: '<!--' + 'A'.repeat(limit) + '-->' }));
  rejects(project({ extra: '<!--' + 'A'.repeat(limit + 1) + '-->' }));
  rejects(project({ extra: '<description><![CDATA[' + '日'.repeat(Math.floor(limit / 3) + 1) + ']]></description>' }));
});

function paddedProject(size) {
  const resources = Array.from({ length: 132 }, (_, i) => resource(String(i), ''));
  let remaining = size - encode(projectText({ resources: resources.join('') })).length;
  for (let i = 0; i < resources.length; i++) {
    const rawSize = Math.min(remaining, 80000);
    resources[i] = resource(String(i), '&#65;'.repeat(Math.floor(rawSize / 5)) + 'A'.repeat(rawSize % 5)); remaining -= rawSize;
  }
  assert.equal(remaining, 0); const source = project({ resources: resources.join('') }); assert.equal(source.length, size); return source;
}
test('actual 10 MiB boundary and generated output size bound', async () => {
  const source = paddedProject(10 * 1024 * 1024), parsed = C.parseProject(source);
  assert.equal((await C.preview(parsed, ONE_DAY)).source_sha256, hash(source));
  const oversized = new Uint8Array(source.length + 1); oversized.set(source); oversized[source.length] = 32; rejects(oversized);
  await assert.rejects(C.preview(parsed, ONE_DAY, ['0']), C.OffDayKitError);
});

test('preview reparses output against text, element and attribute limits before offering a receipt', async () => {
  const sources = [project({ vacations: ' '.repeat(256 * 1024) }), project({ extra: '<roles>' + '<role/>'.repeat(49994) + '</roles>' }), encode(attributeCountBoundary())];
  for (const source of sources) await assert.rejects(C.preview(C.parseProject(source), ONE_DAY, ['0']), C.OffDayKitError);
});

function pythonOracle(cases) {
  const script = `import base64,json,sys\nfrom off_day_kit import parse_project,Recipe,preview,apply,OffDayKitError\nresult=[]\nfor case in json.load(sys.stdin):\n try:\n  p=parse_project(base64.b64decode(case['source']))\n  r=Recipe.from_json(base64.b64decode(case['recipe']))\n  plan=preview(p,r,case['selected'])\n  result.append({'accepted':True,'inventory':p.inventory(),'receipt':plan.to_dict(),'output':base64.b64encode(apply(p,plan) if case['selected'] else p.source).decode()})\n except OffDayKitError:\n  result.append({'accepted':False})\njson.dump(result,sys.stdout)\n`;
  const proc = spawnSync(process.env.PYTHON || 'python3', ['-c', script], { cwd: root, input: JSON.stringify(cases), encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  assert.equal(proc.status, 0, proc.error?.message || proc.stderr); return JSON.parse(proc.stdout);
}

test('independent Python oracle: generated bytes, complete receipt and inventory match across profile cases', async () => {
  const sources = [SOURCE, project(), project({ selfClosing: true }), project({ vacations: vacation() + vacation() }),
    project({ resources: resource('0', 'A&#9;B\r\nC 😀') }),
    project({ tasks: '<taskproperties><taskproperty id="x" valuetype="date" defaultvalue="2027-01-01"/></taskproperties>' + task('0', '<customproperty taskproperty-id="x" value="2027-02-01"/>'),
      extra: '<calendars><date year="2027" month="02" date="02" type="HOLIDAY">Name</date></calendars><previous><previous-tasks><previous-task id="3" start="2027-01-01" duration="1"/></previous-tasks></previous>' })];
  const recipes = [recipeObject(), recipeObject({ weekdays: ['monday', 'sunday'], every_weeks: 1, exclusions: ['2027-01-05'] }),
    recipeObject({ anchor: '2027-02-01', start: '2027-01-01', end: '2027-02-14', exclusions: [] }),
    recipeObject({ anchor: '2028-02-28', start: '2028-02-28', end: '2028-02-29', weekdays: ['monday', 'tuesday'], every_weeks: 1, exclusions: [] })];
  const cases = [];
  for (const source of sources) for (const recipeValue of recipes) for (const selected of [[], ['0']]) cases.push({ source: Buffer.from(source).toString('base64'), recipe: Buffer.from(JSON.stringify(recipeValue)).toString('base64'), selected });
  const answers = pythonOracle(cases);
  for (let i = 0; i < cases.length; i++) {
    const entry = cases[i], parsed = C.parseProject(Buffer.from(entry.source, 'base64')), plan = await C.preview(parsed, C.parseRecipe(Buffer.from(entry.recipe, 'base64')), entry.selected);
    assert.equal(answers[i].accepted, true); assert.deepEqual(await C.inventory(parsed), answers[i].inventory); assert.deepEqual(plan, answers[i].receipt);
    assert.deepEqual(Buffer.from(entry.selected.length ? C.apply(parsed, plan) : parsed.source), Buffer.from(answers[i].output, 'base64'));
  }
});

test('independent Python oracle: seeded XML mutations agree on rejection and accepted semantics', async () => {
  const base = decode(SOURCE), samples = [base];
  let seed = 18371;
  function random(size) { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed % size; }
  const replacements = ['<', '>', '/', '"', "'", '&', '\u0000', ' ', '\n', ':', '='];
  for (let i = 0; i < 240; i++) {
    const at = random(base.length), mode = i % 3, character = replacements[random(replacements.length)];
    samples.push(base.slice(0, at) + (mode === 0 ? '' : character) + base.slice(at + (mode === 2 ? 0 : 1)));
  }
  samples.push(projectText({ resources: resource('0', '&#00000000000000000000000000000000000000000065;') }));
  const encodedRecipe = Buffer.from(JSON.stringify(recipeObject())).toString('base64');
  const cases = samples.map(source => ({ source: Buffer.from(source).toString('base64'), recipe: encodedRecipe, selected: ['0'] }));
  const answers = pythonOracle(cases);
  for (let i = 0; i < cases.length; i++) {
    let parsed, plan, error;
    try { parsed = C.parseProject(Buffer.from(cases[i].source, 'base64')); plan = await C.preview(parsed, recipe(), ['0']); }
    catch (caught) { error = caught; }
    assert.equal(!error, answers[i].accepted, `XML mutation ${i}: ${error?.message}`);
    if (!error) {
      assert.deepEqual(await C.inventory(parsed), answers[i].inventory, `Inventory mutation ${i}`);
      assert.deepEqual(plan, answers[i].receipt, `Receipt mutation ${i}`);
      assert.deepEqual(Buffer.from(C.apply(parsed, plan)), Buffer.from(answers[i].output, 'base64'), `Output mutation ${i}`);
    } else assert.ok(error instanceof C.OffDayKitError);
  }
});

test('accepted native GUI fixture: exact generated bytes, complete saved receipt and second-run no-op', { skip: !process.env.OFFDAY_NATIVE_FIXTURE_DIR }, async () => {
  const directory = process.env.OFFDAY_NATIVE_FIXTURE_DIR, source = readFileSync(join(directory, 'gui-authored.gan'));
  const expected = readFileSync(join(directory, 'generated.gan')), expectedReceipt = JSON.parse(readFileSync(join(directory, 'generated-receipt.json'), 'utf8'));
  const parsed = C.parseProject(source), plan = await C.preview(parsed, recipe(), ['0', '1']), output = C.apply(parsed, plan);
  assert.deepEqual(plan, expectedReceipt); assert.deepEqual(Buffer.from(output), expected);
  assert.equal(plan.output_sha256, '7f7724ac9b1e61b1c8fa7e439b3d6f2e6a0c44d9242b23add07374eff82a0937');
  const fresh = C.parseProject(output), repeated = await C.preview(fresh, recipe(), ['0', '1']);
  assert.equal(repeated.no_op, true); assert.deepEqual(C.apply(fresh, repeated), output);
});
