"""Small, independently handwritten fixtures; no native/vendor fixture copies."""

HEADER = b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
OPEN = b'<project name="Synthetic fixture" version="3.4.3396">'
CLOSE = b'</project>'

A_VACATION = b"<vacation resourceid='0'  end='2027-01-11' start='2027-01-08' />"
B_VACATION = b'<vacation end="2027-02-02" resourceid="1" start="2027-02-01"></vacation>'

# Mixed quotes, CRLF, Unicode, numeric/predefined references, literal fake XML
# inside CDATA, and a trailing comment make lossy XML reserialization visible.
SOURCE = (
    HEADER + OPEN + b'\r\n'
    b'  <!-- Preserve this exact comment and all surrounding whitespace. -->\r\n'
    b'  <description><![CDATA[Literal <vacations/> & project notes]]></description>\r\n'
    b'  <tasks empty-milestones="true">\r\n'
    b'    <task id="10" name="Sentinel &amp; task" start="2027-01-05" duration="3" complete="17" expand="false">\r\n'
    b'      <notes><![CDATA[do not rewrite <vacation resourceid="9"/>]]></notes>\r\n'
    b'    </task>\r\n'
    b'    <task id="11" name="Dependent" start="2027-01-11" duration="1"><depend id="10" type="2"/></task>\r\n'
    b'  </tasks>\r\n'
    b'  <resources>\r\n'
    b'    <resource name="RESOURCEA" id="0"/>\r\n'
    b'    <resource id="1" name="RESOURCEB"/>\r\n' +
    '    <resource id="2" name="RESOURCEC 日本 &amp; &#67;"/>\r\n'.encode('utf-8') +
    b'  </resources>\r\n'
    b'  <allocations><allocation resource-id="0" task-id="10" load="100.0" responsible="true"/></allocations>\r\n'
    b'  <vacations>\r\n    ' + A_VACATION + b'\r\n    ' + B_VACATION + b'\r\n  </vacations>\r\n'
    b'  <roles roleset-name="Synthetic"><role id="0" name="Default"/></roles>\r\n'
    b'</project>\r\n<!-- trailing sentinel -->\r\n'
)


def recipe_dict(**changes):
    result = {
        'weekdays': ['friday'],
        'every_weeks': 2,
        'anchor': '2027-01-04',
        'start': '2027-01-04',
        'end': '2027-02-28',
        'exclusions': ['2027-01-22'],
    }
    result.update(changes)
    return result


def resource(resource_id, name='Resource'):
    return f'<resource id="{resource_id}" name="{name}"/>'.encode('utf-8')


def task(task_id, body=b''):
    return f'<task id="{task_id}" start="2027-01-01" duration="1">'.encode('ascii') + body + b'</task>'


def vacation(resource_id='0', start='2027-01-08', end='2027-01-09'):
    return f'<vacation start="{start}" end="{end}" resourceid="{resource_id}"/>'.encode('ascii')


def project(*, resources=None, tasks=b'', vacations=b'', extra=b'', self_closing=False):
    if resources is None:
        resources = resource('0')
    section = b'<vacations />' if self_closing else b'<vacations>' + vacations + b'</vacations>'
    return OPEN + b'<tasks>' + tasks + b'</tasks><resources>' + resources + b'</resources>' + extra + section + CLOSE


def entity_padded_project(size):
    """Hit an exact raw-byte boundary without violating decoded text limits."""
    resources = [resource(str(i), '') for i in range(132)]
    empty = project(resources=b''.join(resources))
    remaining = size - len(empty)
    if remaining < 0:
        raise ValueError('Requested size is too small')
    for index in range(len(resources)):
        raw_size = min(remaining, 80_000)
        entities, literal = divmod(raw_size, 5)
        name = '&#65;' * entities + 'A' * literal
        resources[index] = resource(str(index), name)
        remaining -= raw_size
    if remaining:
        raise ValueError('Requested size is too large')
    result = project(resources=b''.join(resources))
    assert len(result) == size
    return result
