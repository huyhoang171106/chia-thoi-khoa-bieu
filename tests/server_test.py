"""Scheduling rules, state checks and Excel files, ported from the former Java tests."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import solver, state, validator, xlsx  # noqa: E402


def lock(class_name, shift, day, period, subject, teacher='Lan'):
    return {'className': class_name, 'shift': shift, 'day': day, 'period': period,
            'teacher': teacher, 'subject': subject, 'locked': True}


def assign(class_name, subject, periods, teacher='Lan'):
    return {'className': class_name, 'teacher': teacher, 'subject': subject, 'periods': periods}


def school(classes, teachers, assignments, schedule=(), events=()):
    return {'classes': [{'name': n, 'shift': s} for n, s in classes], 'teachers': list(teachers),
            'assignments': list(assignments), 'events': list(events), 'schedule': list(schedule)}


def sessions(result, teacher='Lan'):
    return {(row['shift'], row['day']) for row in result['schedule'] if row.get('teacher') == teacher}


class Rules(unittest.TestCase):
    def accepted(self, data):
        result = solver.run(data)
        self.assertTrue(result.get('ok'), result)
        validator.check_result(data, result)
        return result

    def rejected(self, data, message=''):
        with self.assertRaisesRegex(ValueError, message):
            validator.validate(data)
        self.assertFalse(solver.run(data).get('ok'))

    def test_cp_solver_and_conflict_report(self):
        def data(rule):
            work = [assign('9/1', 'Toán', 3)] if rule == 1 else [assign('9/1', 'Toán', 2), assign('9/1', 'Sử', 2)]
            return school([('9/1', 'morning')], [{'name': 'Lan', 'sessionRule': str(rule)}], work)
        self.accepted(data(2))
        impossible = solver.run(data(1))
        self.assertEqual(impossible['status'], 'infeasible')
        self.assertIn('Lan', impossible['message'])

    def test_intermediate_timetables_are_valid(self):
        data = school([('9/1', 'morning')], [{'name': 'Lan', 'sessionRule': '2'}],
                      [assign('9/1', 'Toán', 2), assign('9/1', 'Sử', 2)])
        found = []
        self.assertTrue(solver.run(data, report=found.append).get('ok'))
        self.assertTrue(found)
        for result in found:
            validator.check_result(data, result)

    def test_legacy_closed_days_are_ignored(self):
        data = school([('6/1', 'morning')], [{'name': 'Lan', 'maxSessions': 6}],
                      [assign('6/1', 'Toán', 4), assign('6/1', 'Sử', 4)],
                      events=[{'name': 'Chào cờ', 'shift': 'morning', 'day': 0, 'period': 1}])
        data['closed'] = [f'morning:{d}' for d in range(6)]
        result = self.accepted(data)
        self.assertTrue(any(row['subject'] == 'Chào cờ' for row in result['schedule']))
        cleaned = state.clean('{"closed":["morning:0"],"term":"HK1"}')
        self.assertEqual(cleaned, {'term': 'HK1'})

    def test_five_day_week(self):
        data = school([('9/1', 'morning')], [{'name': 'Lan'}], [assign('9/1', 'Toán', 4), assign('9/1', 'Sử', 4)],
                      [lock('9/1', 'morning', 5, 1, 'Toán')])
        result = self.accepted(data)
        self.assertEqual(len(result['schedule']), 8)
        self.assertTrue(all(row['day'] <= 4 and not row.get('locked') for row in result['schedule']))
        data['events'] = [{'name': 'Sinh hoạt', 'shift': 'morning', 'day': 5, 'period': 5}]
        self.rejected(data)

    def test_literature(self):
        def data(locks):
            return school([('6/1', 'morning')], [{'name': 'Lan', 'sessionRule': '2'}],
                          [assign('6/1', 'Văn', 2), assign('6/1', 'Ngữ văn', 2)], locks)
        self.accepted(data([lock('6/1', 'morning', 0, 1, 'Văn'), lock('6/1', 'morning', 0, 2, 'Văn'),
                            lock('6/1', 'morning', 1, 1, 'Ngữ văn'), lock('6/1', 'morning', 1, 2, 'Ngữ văn')]))
        self.rejected(data([lock('6/1', 'morning', 0, 1, 'Văn'), lock('6/1', 'morning', 0, 3, 'Ngữ văn')]), 'liền nhau')

    def test_six_sessions(self):
        data = school([('6/1', 'morning'), ('7/1', 'afternoon')], [{'name': 'Lan', 'sessionRule': '6'}],
                      [assign(c, s, 3) for s in ('Toán', 'Sử') for c in ('6/1', '7/1')],
                      [lock(c, shift, d, 1, 'Toán') for d in range(3) for c, shift in (('6/1', 'morning'), ('7/1', 'afternoon'))])
        self.assertEqual(len(sessions(self.accepted(data))), 6)

    def test_teacher_time_off(self):
        def data(rule):
            return school([('6/1', 'morning')], [{'name': 'Lan', 'offRule': rule}],
                          [assign('6/1', 'Toán', 4), assign('6/1', 'Sử', 4)])
        for rule in ('first', 'session:1:morning', 'day:1'):
            for row in self.accepted(data(rule))['schedule']:
                self.assertFalse(row['period'] == 1 if rule == 'first' else row['day'] == 1, row)
        locked = data('first')
        locked['schedule'] = [lock('6/1', 'morning', 0, 1, 'Toán')]
        self.rejected(locked, 'nghỉ')
        off = validator.unavailable
        self.assertTrue(off({'offRule': 'session:2:afternoon'}, 8, 4))
        self.assertFalse(off({'offRule': 'session:2:afternoon'}, 2, 4))
        self.assertTrue(off({'offRule': 'day:2'}, 2, 4) and off({'offRule': 'day:2'}, 8, 4))

    def test_teacher_gaps(self):
        def data(second_shift, rule, second_period):
            x = school([('6/1', 'morning'), ('6/2', second_shift)], [{'name': 'Lan', 'sessionRule': rule}],
                       [assign('6/1', 'Toán', 1), assign('6/2', 'Văn', 1)],
                       [lock('6/1', 'morning', 0, 1, 'Toán'), lock('6/2', second_shift, 0, second_period, 'Văn')])
            if second_shift == 'afternoon':
                x['assignments'] += [assign('6/1', 'Sử', 1), assign('6/2', 'Sử', 1)]
                x['schedule'] += [lock('6/1', 'morning', 0, 2, 'Sử'), lock('6/2', 'afternoon', 0, 4, 'Sử')]
            return x
        self.accepted(data('morning', '1', 3))
        self.rejected(data('morning', '1', 4), 'trống')
        self.accepted(data('afternoon', '2', 5))

    def test_locked_lessons(self):
        data = school([('9/1', 'morning'), ('9/2', 'morning')], [{'name': 'Lan', 'sessionRule': '3'}],
                      [assign('9/1', 'Toán', 3), assign('9/2', 'Văn', 1), assign('9/1', 'Sử', 3)],
                      [lock('9/1', 'morning', 0, 2, 'Toán')])
        out = self.accepted(data)['schedule']
        self.assertEqual(len(out), 7)
        self.assertEqual(sum(bool(y.get('locked')) and y['day'] == 0 and y['period'] == 2 and y['subject'] == 'Toán'
                             for y in out), 1)
        data['schedule'] = [lock('9/1', 'morning', 0, 2, 'Toán'), lock('9/2', 'morning', 0, 2, 'Văn')]
        self.rejected(data, 'trùng')
        data['schedule'] = [lock('9/1', 'morning', 0, 2, 'Văn')]
        self.rejected(data, 'không khớp')

    def test_single_subject_sessions(self):
        def data(subject, count, periods):
            return school([('9/1', 'morning')], [{'name': 'Lan', 'sessionRule': '1'}], [assign('9/1', subject, count)],
                          [lock('9/1', 'morning', 0, p, subject) for p in periods],
                          [{'name': 'Sinh hoạt', 'shift': 'morning', 'day': 0, 'period': 2}])
        self.accepted(data('Toán', 2, (1, 3)))
        self.rejected(data('Toán', 3, (1, 3, 5)), 'vượt')
        self.rejected(data('Anh', 2, (1, 3)), 'vượt')
        self.assertEqual(solver.subject_group('Anh'), solver.subject_group('Tiếng Anh'))
        self.assertNotEqual(solver.subject_group('Toán'), solver.subject_group('Anh'))

    def test_subject_spacing(self):
        def data(subject, day2, period2, count):
            x = school([('9/1', 'morning')], [{'name': 'Lan', 'sessionRule': '1' if day2 == 0 else '2'}],
                       [assign('9/1', subject, count)],
                       [lock('9/1', 'morning', 0, 1, subject), lock('9/1', 'morning', day2, period2, subject)])
            if count == 3:
                x['schedule'].append(lock('9/1', 'morning', 0, 3, subject))
            if day2:
                x['assignments'] += [assign('9/1', 'A', 1), assign('9/1', 'B', 1)]
                x['schedule'] += [lock('9/1', 'morning', 0, 2, 'A'), lock('9/1', 'morning', day2, 2, 'B')]
            return x
        for args in (('Toán', 1, 1, 2), ('Tiếng Anh', 1, 1, 2), ('Ngữ văn', 0, 2, 2), ('Lịch sử', 2, 1, 2)):
            self.accepted(data(*args))
        self.rejected(data('Lịch sử', 1, 1, 2), '1 ngày')
        self.rejected(data('Toán', 0, 2, 2), 'tiết đôi')
        self.rejected(data('Ngữ văn', 0, 2, 3), 'tối đa 2 tiết Văn')

    def test_subject_aliases_and_integer_periods(self):
        for alias in ('Toan', 'Toán', ' TOÁN '):
            data = school([('9/1', 'morning')], [{'name': 'Lan', 'sessionRule': '1'}],
                          [assign('9/1', 'Toán', 1), assign('9/1', alias, 1)],
                          [lock('9/1', 'morning', 0, 1, 'Toán'), lock('9/1', 'morning', 0, 2, alias)])
            self.rejected(data, 'tiết đôi')
            self.assertEqual(solver.run(data)['status'], 'infeasible')
            data['schedule'][1] = lock('9/1', 'morning', 0, 3, alias)
            data['events'] = [{'name': 'Sinh hoạt', 'shift': 'morning', 'day': 0, 'period': 2}]
            self.accepted(data)
        for value in (2.5, '2.5', 0, 31, True):
            data = school([('9/1', 'morning')], [{'name': 'Lan', 'sessionRule': '1'}], [assign('9/1', 'Văn', value)])
            self.rejected(data, 'số nguyên')
            result = solver.run(data)
            self.assertEqual(result['status'], 'error')
            self.assertIn('số nguyên', result['message'])

    def test_teacher_sessions(self):
        def data(periods, rule=None):
            teacher = {'name': 'Lan', 'sessionRule': rule} if rule else {'name': 'Lan', 'maxSessions': 12}
            return school([('6/1', 'morning')], [teacher, {'name': 'Chưa phân công'}],
                          [assign('6/1', 'Toán', periods), assign('6/1', 'Sử', periods)])
        self.rejected(data(3), '4 buổi')
        self.assertIn(len(sessions(self.accepted(data(4)))), (4, 5))
        external = school([('6/1', 'morning')], [{'name': 'Lan', 'sessionRule': '1'}], [assign('6/1', 'Văn', 2)])
        self.assertEqual(len(sessions(self.accepted(external))), 1)
        self.rejected(data(6, '1'))

    def test_opposite_shift_activities(self):
        experience, sport = 'Hoạt động trải nghiệm', 'Thể dục'
        data = school([('6/1', 'morning'), ('7/1', 'afternoon')],
                      [{'name': 'Lan', 'sessionRule': '2'}, {'name': 'Minh', 'sessionRule': '2'}],
                      [assign(c, s, 2, t) for c in ('6/1', '7/1') for s, t in ((experience, 'Lan'), (sport, 'Minh'))],
                      [lock('6/1', 'afternoon', 1, 1, experience)])
        out = self.accepted(data)['schedule']
        for c, shift in (('6/1', 'afternoon'), ('7/1', 'morning')):
            extra = sorted((y for y in out if y['className'] == c and solver.extra_kind(y['subject'])),
                           key=lambda y: y['period'])
            self.assertEqual([y['period'] for y in extra], [1, 2, 3, 4])
            self.assertEqual({(y['shift'], y['day']) for y in extra}, {(shift, extra[0]['day'])})
            self.assertEqual(extra[0]['subject'], extra[1]['subject'])
            self.assertEqual(extra[2]['subject'], extra[3]['subject'])
        self.assertTrue(any(y.get('locked') and y['className'] == '6/1' and y['day'] == 1 and y['period'] == 1 for y in out))
        data['schedule'] = [lock('6/1', 'morning', 1, 1, experience)]
        self.rejected(data, 'không khớp')


class StateChecks(unittest.TestCase):
    def test_teacher_names(self):
        state.check_teacher_names({'teachers': [{'name': 'Cô Lan'}, {'name': 'Cô Lân'}, {'name': ''}]})
        with self.assertRaisesRegex(ValueError, 'trùng'):
            state.check_teacher_names({'teachers': [{'name': 'Cô Lan'}, {'name': '  cô   lan '}]})


class Excel(unittest.TestCase):
    def test_school_export(self):
        def row(c, shift, day, period, subject, teacher):
            return {'className': c, 'shift': shift, 'day': day, 'period': period, 'subject': subject, 'teacher': teacher}
        data = {'term': 'Học kỳ I & II',
                'classes': [{'name': '6/10', 'shift': 'morning'}, {'name': '6/2', 'shift': 'morning', 'grade': '6'},
                            {'name': '7A1', 'shift': 'afternoon'}, {'name': 'Khác', 'shift': 'morning'}],
                'events': [{'name': 'Chào cờ', 'shift': 'morning', 'day': 0, 'period': 1}],
                'schedule': [row('6/2', 'morning', 0, 2, 'Toán & Lý', 'Cô <Lan>'), row('6/2', 'afternoon', 2, 4, 'Thể dục', 'Thầy An'),
                             row('7A1', 'afternoon', 4, 5, '=1+1', 'Giáo viên'), row('6/10', 'morning', 0, 1, 'Chào cờ', '')]}
        book = xlsx.school_workbook(data)
        # tests/school_export_test.py inspects this file.
        (ROOT / 'build').mkdir(exist_ok=True)
        (ROOT / 'build' / 'test-school-export.xlsx').write_bytes(book)
        rows = xlsx.read(book)
        self.assertTrue(rows[3][2].startswith('6/2'))
        self.assertEqual(rows[5][2], 'Toán & Lý\nCô <Lan>')
        data['schedule'] = [row('6/2', 'morning', 0, 2, 'Toán', 'Lan'), row('6/2', 'morning', 0, 2, 'Văn', 'Mai')]
        with self.assertRaisesRegex(ValueError, 'hai nội dung'):
            xlsx.school_workbook(data)

    def test_row_gaps_and_unsafe_xml(self):
        import io
        import zipfile

        def book(sheet):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as z:
                z.writestr('xl/workbook.xml', "<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' "
                           "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>"
                           "<sheets><sheet name='Sheet1' sheetId='1' r:id='rId1'/></sheets></workbook>")
                z.writestr('xl/_rels/workbook.xml.rels', "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/"
                           "relationships'><Relationship Id='rId1' Target='worksheets/sheet1.xml'/></Relationships>")
                z.writestr('xl/worksheets/sheet1.xml', sheet)
            return buffer.getvalue()
        ns = "xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'"
        rows = xlsx.read(book(f"<worksheet {ns}><sheetData><row r='1'><c r='A1' t='inlineStr'><is><t>Giáo viên</t></is></c></row>"
                              "<row r='2'><c r='A2' t='inlineStr'><is><t>T.Sương</t></is></c></row>"
                              "<row r='4'><c r='B4' t='inlineStr'><is><t>9/2</t></is></c></row></sheetData></worksheet>"))
        self.assertEqual(rows, [['Giáo viên'], ['T.Sương'], [], ['', '9/2']])
        with self.assertRaisesRegex(ValueError, 'không hợp lệ'):
            xlsx.read(book(f"<!DOCTYPE x [<!ENTITY a 'b'>]><worksheet {ns}><sheetData/></worksheet>"))


if __name__ == '__main__':
    unittest.main()
