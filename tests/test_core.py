"""Black-box properties and adversarial bounds for the public core API."""

from dataclasses import replace
from datetime import date
import hashlib
import json
import unittest

from off_day_kit import OffDayKitError, Recipe, apply, parse_project, preview
from tests.fixtures import (
    A_VACATION, B_VACATION, SOURCE, entity_padded_project, project,
    recipe_dict, resource, task, vacation,
)


class HappyPathTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE
        self.project = parse_project(self.source)
        self.recipe = Recipe.from_dict(recipe_dict())

    def test_independent_fortnight_fixture_has_exact_five_additions(self):
        plan = preview(self.project, self.recipe, ['0', '1'])
        self.assertEqual(
            [(v.resource_id, v.start.isoformat(), v.end.isoformat()) for v in plan.additions],
            [('0', '2027-02-05', '2027-02-06'), ('0', '2027-02-19', '2027-02-20'),
             ('1', '2027-01-08', '2027-01-09'), ('1', '2027-02-05', '2027-02-06'),
             ('1', '2027-02-19', '2027-02-20')],
        )
        receipt = plan.to_dict()
        self.assertEqual(receipt['addition_count'], 5)
        self.assertEqual(receipt['existing_interval_count'], 2)
        self.assertEqual(receipt['output_interval_count'], 7)
        self.assertEqual(receipt['selected_resource_ids'], ['0', '1'])
        self.assertEqual(receipt['candidate_dates'], [
            {'date': '2027-01-08', 'excluded': False},
            {'date': '2027-01-22', 'excluded': True},
            {'date': '2027-02-05', 'excluded': False},
            {'date': '2027-02-19', 'excluded': False},
        ])
        by_resource = {(c['resource_id'], c['date']): c for c in receipt['candidates_by_resource']}
        self.assertEqual(by_resource['0', '2027-01-08']['status'], 'covered')
        self.assertEqual(by_resource['1', '2027-01-08']['status'], 'add')
        self.assertEqual(by_resource['0', '2027-01-22']['status'], 'excluded')
        self.assertFalse(receipt['no_op'])

    def test_bytes_outside_vacations_and_existing_records_are_unchanged(self):
        plan = preview(self.project, self.recipe, ['0', '1'])
        output = apply(self.project, plan)
        # Independent literal delimiters avoid testing against parser offsets.
        opening = self.source.index(b'  <vacations>')
        end = self.source.index(b'</vacations>', opening) + len(b'</vacations>')
        new_opening = output.index(b'  <vacations>')
        new_end = output.index(b'</vacations>', new_opening) + len(b'</vacations>')
        self.assertEqual(output[:new_opening], self.source[:opening])
        self.assertEqual(output[new_end:], self.source[end:])
        self.assertEqual(output.count(A_VACATION), 1)
        self.assertEqual(output.count(B_VACATION), 1)
        self.assertIn(b'\r\n    ' + A_VACATION + b'\r\n    ' + B_VACATION + b'\r\n  ', output)
        reparsed = parse_project(output)
        self.assertEqual(len(reparsed.intervals), 7)
        self.assertFalse(any(v.resource_id == '2' for v in reparsed.intervals))

    def test_hashes_are_of_exact_source_and_output_bytes(self):
        plan = preview(self.project, self.recipe, ['1'])
        receipt = plan.to_dict()
        self.assertEqual(receipt['source_sha256'], hashlib.sha256(SOURCE).hexdigest())
        self.assertEqual(receipt['output_sha256'], hashlib.sha256(apply(self.project, plan)).hexdigest())

    def test_reapplying_recipe_is_byte_identical_no_op(self):
        first = apply(self.project, preview(self.project, self.recipe, ['0', '1']))
        fresh = parse_project(first)
        plan = preview(fresh, self.recipe, ['1', '0'])
        self.assertEqual(plan.additions, ())
        self.assertTrue(plan.to_dict()['no_op'])
        self.assertEqual(apply(fresh, plan), first)

    def test_selection_order_is_numeric_and_deterministic(self):
        source = project(resources=resource('10') + resource('2') + resource('0'))
        parsed = parse_project(source)
        first = preview(parsed, self.recipe, ['10', '0', '2'])
        second = preview(parsed, self.recipe, ['2', '10', '0'])
        self.assertEqual(first, second)
        self.assertEqual(first.selected_ids, ('0', '2', '10'))
        self.assertEqual(apply(parsed, first), apply(parsed, second))

    def test_empty_selection_previews_but_does_not_authorize_apply(self):
        plan = preview(self.project, self.recipe)
        self.assertEqual(plan.additions, ())
        self.assertEqual(plan.candidates, ())
        self.assertEqual(plan.to_dict()['source_sha256'], plan.to_dict()['output_sha256'])
        self.assertEqual(len(plan.to_dict()['candidate_dates']), 4)
        with self.assertRaises(OffDayKitError):
            apply(self.project, plan)

    def test_self_closing_section_can_expand_without_other_byte_changes(self):
        source = project(self_closing=True)
        parsed = parse_project(source)
        plan = preview(parsed, self.recipe, ['0'])
        output = apply(parsed, plan)
        before, after = source.split(b'<vacations />')
        self.assertTrue(output.startswith(before))
        self.assertTrue(output.endswith(after))
        self.assertEqual(len(parse_project(output).intervals), 3)

    def test_no_candidates_preserves_self_closing_section_exactly(self):
        source = project(self_closing=True)
        parsed = parse_project(source)
        recipe = Recipe.from_dict(recipe_dict(start='2027-01-04', end='2027-01-04', exclusions=[]))
        plan = preview(parsed, recipe, ['0'])
        self.assertEqual(apply(parsed, plan), source)

    def test_vacation_exclusive_end_is_not_covered(self):
        parsed = parse_project(project(vacations=vacation(start='2027-01-07', end='2027-01-08')))
        recipe = Recipe.from_dict(recipe_dict(start='2027-01-08', end='2027-01-08', exclusions=[]))
        plan = preview(parsed, recipe, ['0'])
        self.assertEqual(len(plan.additions), 1)
        self.assertEqual(plan.additions[0].start, date(2027, 1, 8))

    def test_exclusion_wins_when_existing_vacation_also_covers_date(self):
        recipe = Recipe.from_dict(recipe_dict(start='2027-01-08', end='2027-01-08', exclusions=['2027-01-08']))
        plan = preview(self.project, recipe, ['0'])
        candidate = plan.to_dict()['candidates_by_resource'][0]
        self.assertTrue(candidate['covered'])
        self.assertTrue(candidate['excluded'])
        self.assertEqual(candidate['status'], 'excluded')
        self.assertEqual(apply(self.project, plan), SOURCE)

    def test_literal_markup_inside_text_does_not_confuse_section_offsets(self):
        inventory = self.project.inventory()
        self.assertEqual([r['id'] for r in inventory['resources']], ['0', '1', '2'])
        self.assertEqual(inventory['resources'][2]['name'], 'RESOURCEC 日本 & C')
        self.assertEqual(inventory['existing_interval_count'], 2)
        self.assertEqual([v.raw for v in self.project.intervals], [A_VACATION, B_VACATION])

    def test_forward_resource_and_dependency_references_are_resolved(self):
        source = (
            b'<project version="3.4.3396"><vacations>' + vacation() + b'</vacations>'
            b'<tasks>' + task('1', b'<depend id="2"/>') + task('2') + b'</tasks>'
            b'<allocations><allocation task-id="2" resource-id="0"/></allocations>'
            b'<resources>' + resource('0') + b'</resources></project>'
        )
        self.assertEqual(len(parse_project(source).intervals), 1)


class RecipeValidationTests(unittest.TestCase):
    def test_fortnight_cadence_extends_backwards_from_anchor(self):
        recipe = Recipe.from_dict(recipe_dict(anchor='2027-02-01', start='2027-01-01', end='2027-02-14', exclusions=[]))
        dates = preview(parse_project(project()), recipe).to_dict()['candidate_dates']
        self.assertEqual([v['date'] for v in dates], ['2027-01-08', '2027-01-22', '2027-02-05'])

    def test_week_window_endpoints_and_leap_day_are_inclusive(self):
        recipe = Recipe.from_dict(recipe_dict(weekdays=['monday', 'tuesday'], every_weeks=1,
            anchor='2028-02-28', start='2028-02-28', end='2028-02-29', exclusions=[]))
        parsed = parse_project(project())
        self.assertEqual([i.start.isoformat() for i in preview(parsed, recipe, ['0']).additions], ['2028-02-28', '2028-02-29'])

    def test_366_day_window_and_last_supported_date(self):
        Recipe.from_dict(recipe_dict(start='2028-01-01', end='2028-12-31', exclusions=[]))
        recipe = Recipe.from_dict(recipe_dict(weekdays=['monday'], every_weeks=1,
            anchor='2199-12-30', start='2199-12-30', end='2199-12-30', exclusions=[]))
        plan = preview(parse_project(project()), recipe, ['0'])
        self.assertEqual(plan.additions[0].end, date(2199, 12, 31))

    def test_modern_planning_range_applies_to_every_recipe_date(self):
        first = Recipe.from_dict(recipe_dict(weekdays=['monday'], every_weeks=1,
            anchor='1900-01-01', start='1900-01-01', end='1900-01-01', exclusions=[]))
        self.assertEqual(preview(parse_project(project()), first, ['0']).additions[0].end, date(1900, 1, 2))
        for field, value in [('anchor', '0001-01-01'), ('anchor', '1899-12-25'),
                             ('start', '1582-10-10'), ('start', '1899-12-31'),
                             ('end', '2200-01-01'), ('exclusions', ['1582-10-10'])]:
            with self.subTest(field=field, value=value), self.assertRaises(OffDayKitError):
                Recipe.from_dict(recipe_dict(**{field: value}))
        with self.assertRaises(OffDayKitError):
            Recipe((0,), 1, date(1, 1, 1), date(2027, 1, 4), date(2027, 1, 5), ())
        with self.assertRaises(OffDayKitError):
            Recipe.from_dict(recipe_dict(anchor='2199-12-30', start='2199-12-31', end='2199-12-31', exclusions=[]))

    def test_round_trip_is_deterministic_without_resource_selection(self):
        recipe = Recipe.from_dict(recipe_dict(weekdays=['sunday', 'monday'], exclusions=['2027-02-01', '2027-01-22']))
        self.assertEqual(Recipe.from_dict(recipe.to_dict()), recipe)
        self.assertEqual(recipe.to_dict()['weekdays'], ['monday', 'sunday'])
        self.assertEqual(set(recipe.to_dict()), {'weekdays', 'every_weeks', 'anchor', 'start', 'end', 'exclusions'})

    def test_recipe_requires_exact_fields_and_types(self):
        invalid = [None, [], {}, recipe_dict(resource_ids=['0']),
                   {k: v for k, v in recipe_dict().items() if k != 'exclusions'}]
        changes = [
            {'weekdays': []}, {'weekdays': ['Friday']}, {'weekdays': ['fri']}, {'weekdays': [4]},
            {'weekdays': 'friday'}, {'weekdays': ('friday',)}, {'weekdays': ['friday', 'friday']},
            {'every_weeks': True}, {'every_weeks': 0}, {'every_weeks': 3}, {'every_weeks': 1.0}, {'every_weeks': '2'},
            {'anchor': '2027-01-05'}, {'start': '2027-03-01'}, {'end': '2028-01-05'},
            {'start': '2027-1-04'}, {'end': '2027-02-29'}, {'anchor': '2027-01-04T00:00:00'},
            {'end': '9999-12-31', 'start': '9999-12-31', 'exclusions': []},
            {'exclusions': '2027-01-22'}, {'exclusions': None}, {'exclusions': [1]},
            {'exclusions': ['2027-01-22', '2027-01-22']}, {'exclusions': ['2027-03-01']},
            {'exclusions': ['2027-01-22'] * 367},
        ]
        invalid.extend(recipe_dict(**change) for change in changes)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(OffDayKitError):
                    Recipe.from_dict(value)

    def test_json_rejects_duplicate_keys_nonfinite_invalid_utf8_and_oversize(self):
        valid = json.dumps(recipe_dict()).encode()
        self.assertEqual(Recipe.from_json(valid), Recipe.from_dict(recipe_dict()))
        invalid = [b'\xff', b'{}x', valid[:-1] + b', "every_weeks": 1}',
                   valid.replace(b'"every_weeks": 2', b'"every_weeks": NaN'), b' ' * 65_537]
        for value in invalid:
            with self.subTest(value=value[:100]):
                with self.assertRaises(OffDayKitError):
                    Recipe.from_json(value)

    def test_huge_json_integer_is_a_normal_validation_error(self):
        value = json.dumps(recipe_dict()).encode().replace(b'"every_weeks": 2', b'"every_weeks": ' + b'1' * 5_000)
        with self.assertRaises(OffDayKitError):
            Recipe.from_json(value)


class ParserRejectionTests(unittest.TestCase):
    def reject(self, source):
        with self.assertRaises(OffDayKitError):
            parse_project(source)

    def test_requires_bytes_and_one_well_formed_project(self):
        for source in [None, '<project/>', bytearray(project()), b'', b'<project>', project() + project(), b'<other/>']:
            with self.subTest(source=str(source)[:80]):
                self.reject(source)

    def test_rejects_unknown_version_elements_attributes_and_structure(self):
        sources = [
            project().replace(b'3.4.3396', b'3.4.3397'),
            project().replace(b' version="3.4.3396"', b''),
            project(extra=b'<unexpected/>'),
            project().replace(b'<resources>', b'<resources surprise="true">'),
            project(resources=task('0')),
            project(tasks=resource('0')),
            project(vacations=b'<resource id="0" name="Wrong section"/>'),
            project(extra=b'<tasks/>'),
            project(extra=b'<resources/>'),
            project(extra=b'<vacations/>'),
            project().replace(b'<resources>', b'<resources>unexpected text'),
        ]
        for source in sources:
            with self.subTest(source=source):
                self.reject(source)

    def test_all_three_core_sections_are_required(self):
        for section in [b'<tasks></tasks>', b'<resources><resource id="0" name="Resource"/></resources>', b'<vacations></vacations>']:
            with self.subTest(section=section):
                self.reject(project().replace(section, b''))

    def test_duplicate_ids_are_rejected_including_nested_tasks(self):
        self.reject(project(resources=resource('0') + resource('0', 'Different name')))
        self.reject(project(tasks=task('1') + task('1')))
        self.reject(project(tasks=task('1', task('1'))))

    def test_resource_ids_are_canonical_32bit_decimal_strings(self):
        for value in ['00', '01', '-1', '+1', ' 1', '1 ', '1.0', '0x1', '2147483648', '١', '']:
            with self.subTest(value=value):
                self.reject(project(resources=resource(value)))
        self.assertEqual(parse_project(project(resources=resource('2147483647'))).resources[0].id, '2147483647')

    def test_task_ids_and_required_attributes_are_validated(self):
        for body in [b'<task id="01" start="2027-01-01" duration="1"/>',
                     b'<task id="0" start="2027-01-01"/>',
                     b'<task id="0" duration="1"/>',
                     b'<task id="0" start="2027-01-01" duration="-1"/>',
                     b'<task id="0" start="2027-01-01" duration="2147483648"/>',
                     b'<task id="0" start="2027-01-01" duration="1.0"/>']:
            with self.subTest(body=body):
                self.reject(project(tasks=body))
        self.reject(project(resources=b'<resource id="0"/>'))
        self.reject(project(resources=b'<resource name="Missing ID"/>'))

    def test_huge_task_duration_is_a_normal_validation_error(self):
        self.reject(project(tasks=b'<task id="0" start="2027-01-01" duration="' + b'1' * 5_000 + b'"/>'))

    def test_dangling_vacation_allocation_and_dependency_references(self):
        sources = [
            project(vacations=vacation('9')),
            project(tasks=task('0'), extra=b'<allocations><allocation task-id="9" resource-id="0"/></allocations>'),
            project(tasks=task('0'), extra=b'<allocations><allocation task-id="0" resource-id="9"/></allocations>'),
            project(tasks=task('0', b'<depend id="9"/>')),
            project(tasks=task('0'), extra=b'<allocations><allocation resource-id="0"/></allocations>'),
        ]
        for source in sources:
            with self.subTest(source=source):
                self.reject(source)

    def test_vacation_dates_and_required_attributes(self):
        sources = [vacation(start='2027-02-29'), vacation(start='2027-1-08'),
                   vacation(start='0000-01-01'), vacation(end='2027-01-08'), vacation(end='2027-01-07'),
                   vacation(end='2027-01-09T00:00:00'), b'<vacation start="2027-01-08" resourceid="0"/>',
                   b'<vacation end="2027-01-09" resourceid="0"/>',
                   b'<vacation start="2027-01-08" end="2027-01-09"/>']
        for body in sources:
            with self.subTest(body=body):
                self.reject(project(vacations=body))

    def test_task_project_calendar_and_custom_dates_are_validated(self):
        sources = [
            project().replace(b'<project ', b'<project view-date="2027-02-29" '),
            project(tasks=task('0').replace(b'2027-01-01', b'2027-02-29')),
            project(tasks=task('0').replace(b'id="0"', b'id="0" thirdDate="2027-02-29"')),
            project(extra=b'<calendars><date year="2027" month="2" date="29" type="1"/></calendars>'),
            project(extra=b'<calendars><date year="*" month="1" date="1" type="1"/></calendars>'),
            project(tasks=b'<taskproperties><taskproperty id="x" valuetype="date" defaultvalue="2027-02-29"/></taskproperties>'),
            project(tasks=b'<taskproperties><taskproperty id="x" valuetype="date"/></taskproperties>' + task('0', b'<customproperty taskproperty-id="x" value="2027-02-29"/>')),
            project(resources=b'<custom-property-definition id="x" type="date" default-value="2027-02-29"/>' + resource('0')),
        ]
        for source in sources:
            with self.subTest(source=source):
                self.reject(source)

    def test_modern_planning_range_applies_to_every_recognized_xml_date(self):
        for invalid in ['0001-01-01', '1582-10-10', '1899-12-31', '2200-01-01']:
            value = invalid.encode()
            year, month, day = invalid.split('-')
            cases = [
                project(vacations=vacation(start=invalid)),
                project(vacations=vacation(end=invalid)),
                project().replace(b'<project ', b'<project view-date="' + value + b'" '),
                project(tasks=task('0').replace(b'2027-01-01', value)),
                project(tasks=task('0').replace(b'id="0"', b'id="0" thirdDate="' + value + b'"')),
                project(extra=b'<previous><previous-tasks name="baseline"><previous-task id="0" start="' + value + b'" duration="1"/></previous-tasks></previous>'),
                project(extra=f'<calendars><date year="{year}" month="{int(month)}" date="{int(day)}" type="HOLIDAY"/></calendars>'.encode()),
                project(tasks=b'<taskproperties><taskproperty id="x" valuetype="date" defaultvalue="' + value + b'"/></taskproperties>'),
                project(tasks=b'<taskproperties><taskproperty id="x" valuetype="date"/></taskproperties>' + task('0', b'<customproperty taskproperty-id="x" value="' + value + b'"/>')),
                project(resources=b'<custom-property-definition id="x" type="date" default-value="' + value + b'"/>' + resource('0')),
                project(resources=b'<custom-property-definition id="x" type="date"/><resource id="0" name="R"><custom-property definition-id="x" value="' + value + b'"/></resource>'),
            ]
            for case in cases:
                with self.subTest(invalid=invalid, case=case): self.reject(case)
        for valid in ['1900-01-01', '2199-12-31']:
            parse_project(project().replace(b'<project ', b'<project view-date="' + valid.encode() + b'" '))
            parse_project(project(tasks=task('0').replace(b'2027-01-01', valid.encode())))

    def test_duplicate_or_dangling_custom_properties(self):
        sources = [
            project(tasks=b'<taskproperties><taskproperty id="x"/><taskproperty id="x"/></taskproperties>'),
            project(tasks=task('0', b'<customproperty taskproperty-id="missing" value="x"/>')),
            project(resources=b'<custom-property-definition id="x"/><custom-property-definition id="x"/>' + resource('0')),
            project(resources=b'<resource id="0" name="R"><custom-property definition-id="missing" value="x"/></resource>'),
        ]
        for source in sources:
            with self.subTest(source=source):
                self.reject(source)

    def test_dtd_custom_entities_processing_instructions_namespaces_and_boms(self):
        sources = [
            b'<!DOCTYPE project>' + project(),
            b'<!DOCTYPE project [<!ENTITY x "expansion">]>' + project(),
            b'<!DOCTYPE project SYSTEM "file:///etc/passwd">' + project(),
            b'<?target data?>' + project(),
            project(extra=b'<?target data?>'),
            project().replace(b'<project ', b'<project xmlns="urn:test" '),
            project().replace(b'<project ', b'<project xmlns:x="urn:test" '),
            project().replace(b'<resources>', b'<x:resources>').replace(b'</resources>', b'</x:resources>'),
            b'\xef\xbb\xbf' + project(), b'\xff\xfe' + project(), b'\xfe\xff' + project(),
            b'<?xml version="1.1"?>' + project(),
            b'<?xml version="1.0" encoding="ISO-8859-1"?>' + project(),
            project(resources=resource('0', 'name').replace(b'name="name"', b'name="\xff"')),
            project(resources=resource('0', '&custom;')),
        ]
        for source in sources:
            with self.subTest(source=source[:120]):
                self.reject(source)

    def test_comments_and_cdata_elsewhere_are_accepted_and_preserved(self):
        source = project(tasks=task('0', b'<notes><![CDATA[a < b && c > d]]></notes>'),
                         extra=b'<!-- valid outside vacations --><description><![CDATA[<vacations/>]]></description>')
        parsed = parse_project(source)
        recipe = Recipe.from_dict(recipe_dict(start='2027-01-04', end='2027-01-04', exclusions=[]))
        self.assertEqual(apply(parsed, preview(parsed, recipe, ['0'])), source)
        self.reject(project(vacations=b'<!-- ambiguous editable content -->'))
        self.reject(project(vacations=b'<![CDATA[ ]]>'))


class IntegrityAndLimitTests(unittest.TestCase):
    def setUp(self):
        self.recipe = Recipe.from_dict(recipe_dict(start='2027-01-08', end='2027-01-08', exclusions=[]))

    def test_apply_rejects_a_different_source_even_if_semantically_equal(self):
        original = parse_project(project())
        plan = preview(original, self.recipe, ['0'])
        changed = parse_project(project().replace(b'<tasks>', b'<tasks> '))
        with self.assertRaises(OffDayKitError):
            apply(changed, plan)

    def test_apply_recomputes_and_rejects_tampered_plan_fields(self):
        parsed = parse_project(project())
        plan = preview(parsed, self.recipe, ['0'])
        for altered in [replace(plan, additions=()), replace(plan, output_sha256='0' * 64),
                        replace(plan, existing_interval_count=123), replace(plan, candidates=()),
                        replace(plan, selected_ids=()), replace(plan, source_sha256='0' * 64)]:
            with self.subTest(altered=altered):
                with self.assertRaises(OffDayKitError):
                    apply(parsed, altered)

    def test_selection_rejects_unknown_duplicate_and_noncanonical_ids(self):
        parsed = parse_project(project())
        for selection in [['9'], ['0', '0'], ['00'], [0], [True], ['-1'], ['2147483648']]:
            with self.subTest(selection=selection):
                with self.assertRaises(OffDayKitError):
                    preview(parsed, self.recipe, selection)

    def test_exactly_100_selections_succeed_and_101_fail(self):
        parsed = parse_project(project(resources=b''.join(resource(str(i)) for i in range(101))))
        plan = preview(parsed, self.recipe, (str(i) for i in range(100)))
        self.assertEqual(len(plan.additions), 100)
        self.assertEqual(len(parse_project(apply(parsed, plan)).intervals), 100)
        with self.assertRaises(OffDayKitError):
            preview(parsed, self.recipe, (str(i) for i in range(101)))

    def test_existing_interval_limit_and_bounded_overlapping_coverage_receipt(self):
        source = project(vacations=vacation() * 10_000)
        parsed = parse_project(source)
        plan = preview(parsed, self.recipe, ['0'])
        self.assertEqual(len(parsed.intervals), 10_000)
        self.assertEqual(plan.additions, ())
        self.assertEqual(apply(parsed, plan), source)
        encoded = json.dumps(plan.to_dict()).encode()
        self.assertLess(len(encoded), 10_000, 'One candidate must not repeat 10000 covering records')
        row = plan.to_dict()['candidates_by_resource'][0]
        self.assertEqual(row['covering_interval_count'], 10_000)
        self.assertEqual(row['covering_interval_example'], {
            'resource_id': '0', 'start': '2027-01-08', 'end_exclusive': '2027-01-09'})
        with self.assertRaises(OffDayKitError):
            parse_project(project(vacations=vacation() * 10_001))

    def test_generated_intervals_share_the_10000_total_limit(self):
        parsed = parse_project(project(vacations=vacation(start='2027-01-01', end='2027-01-02') * 9_999))
        plan = preview(parsed, self.recipe, ['0'])
        self.assertEqual(len(parse_project(apply(parsed, plan)).intervals), 10_000)
        two_dates = Recipe.from_dict(recipe_dict(start='2027-01-08', end='2027-01-22', exclusions=[]))
        with self.assertRaises(OffDayKitError):
            preview(parsed, two_dates, ['0'])

    def test_actual_10mib_input_boundary_and_generated_output_bound(self):
        limit = 10 * 1024 * 1024
        source = entity_padded_project(limit)
        parsed = parse_project(source)
        self.assertEqual(preview(parsed, self.recipe).source_sha256, hashlib.sha256(source).hexdigest())
        with self.assertRaises(OffDayKitError):
            parse_project(source + b' ')
        with self.assertRaises(OffDayKitError):
            preview(parsed, self.recipe, ['0'])

    def test_actual_depth_boundary(self):
        def nested(count):
            body = b''
            for i in range(count):
                body = task(str(i), body)
            return project(tasks=body)
        parse_project(nested(30))  # project + tasks + 30 task levels = 32
        with self.assertRaises(OffDayKitError):
            parse_project(nested(31))

    def test_actual_element_count_boundary(self):
        # project, tasks, resources, resource, roles, vacations = 6 elements.
        parse_project(project(extra=b'<roles>' + b'<role/>' * 49_994 + b'</roles>'))
        with self.assertRaises(OffDayKitError):
            parse_project(project(extra=b'<roles>' + b'<role/>' * 49_995 + b'</roles>'))

    @staticmethod
    def project_at_attribute_count_limit():
        # The outer project and one resource contribute four attributes.
        # 22221 nine-attribute tasks and one seven-attribute task add 199996.
        body = b''.join(
            f'<task id="{i}" start="2027-01-01" duration="1" name="" color="" shape="" complete="0" priority="0" uid=""/>'.encode()
            for i in range(22_221)
        )
        last = b'<task id="22221" start="2027-01-01" duration="1" name="" color="" shape="" complete="0"/>'
        return project(tasks=body + last)

    def test_actual_total_attribute_count_boundary(self):
        source = self.project_at_attribute_count_limit()
        parse_project(source)
        with self.assertRaises(OffDayKitError):
            parse_project(source.replace(b'id="22221"', b'id="22221" uid="extra"'))

    def test_preview_rejects_generated_output_crossing_other_parser_limits(self):
        sources = [
            ('vacations text', project(vacations=b' ' * (256 * 1024))),
            ('element count', project(extra=b'<roles>' + b'<role/>' * 49_994 + b'</roles>')),
            ('attribute count', self.project_at_attribute_count_limit()),
        ]
        for label, source in sources:
            with self.subTest(limit=label):
                parsed = parse_project(source)
                with self.assertRaises(OffDayKitError):
                    preview(parsed, self.recipe, ['0'])

    def test_actual_individual_attribute_boundary(self):
        # The limit includes the UTF-8 bytes of attribute name "name".
        parse_project(project(resources=resource('0', 'A' * (16_384 - 4))))
        with self.assertRaises(OffDayKitError):
            parse_project(project(resources=resource('0', 'A' * (16_384 - 3))))
        with self.assertRaises(OffDayKitError):
            parse_project(project(resources=resource('0', '日' * 5_461)))

    def test_actual_total_attribute_bytes_limit(self):
        with self.assertRaises(OffDayKitError):
            parse_project(project(resources=b''.join(resource(str(i), 'A' * 16_000) for i in range(263))))

    def test_actual_node_text_and_total_text_limits(self):
        parse_project(project(extra=b'<description>' + b'A' * (256 * 1024) + b'</description>'))
        with self.assertRaises(OffDayKitError):
            parse_project(project(extra=b'<description>' + b'A' * (256 * 1024 + 1) + b'</description>'))
        each = b'<notes>' + b'A' * (256 * 1024) + b'</notes>'
        parse_project(project(tasks=b''.join(task(str(i), each) for i in range(8))))
        with self.assertRaises(OffDayKitError):
            parse_project(project(tasks=b''.join(task(str(i), each) for i in range(9))))

    def test_comment_size_is_bounded_even_though_comments_are_preserved(self):
        parse_project(project(extra=b'<!--' + b'A' * (256 * 1024) + b'-->'))
        with self.assertRaises(OffDayKitError):
            parse_project(project(extra=b'<!--' + b'A' * (256 * 1024 + 1) + b'-->'))


if __name__ == '__main__':
    unittest.main()
