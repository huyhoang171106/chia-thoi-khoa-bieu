import importlib.util
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build' / 'vendor'))
sys.path.insert(0, str(ROOT / 'scripts'))
import cp_scheduler

HAS_ORTOOLS = importlib.util.find_spec('ortools') is not None


@unittest.skipUnless(HAS_ORTOOLS, 'OR-Tools is not installed')
class TimetableSolverTest(unittest.TestCase):
    def fixture(self, subject='Toán', periods=2, session_rule='2'):
        return {'classes': [{'name': '9/1', 'shift': 'morning'}],
                'teachers': [{'name': 'Lan', 'sessionRule': session_rule}],
                'assignments': [{'className': '9/1', 'teacher': 'Lan',
                                 'subject': subject, 'periods': periods}],
                'events': [], 'schedule': []}

    def test_math_spread_and_teacher_session_count(self):
        state = self.fixture()
        state['assignments'].append(dict(className='9/1', teacher='Lan', subject='Sử', periods=2))
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['singleMath'])
        self.assertEqual(len({(x['shift'], x['day']) for x in result['schedule']}), 2)
        for day in {x['day'] for x in result['schedule']}:
            self.assertGreaterEqual(sum(x['day'] == day for x in result['schedule']), 2)

    def test_math_aliases_cannot_bypass_adjacent_lesson_rule(self):
        for alias in ('Toan', 'Toa\u0301n', ' TOÁN '):
            with self.subTest(alias=alias):
                state = self.fixture(periods=1, session_rule='1')
                state['assignments'].append(dict(className='9/1', teacher='Lan', subject=alias, periods=1))
                self.assertEqual(cp_scheduler.solve(state, time_limit=10)['status'], 'infeasible')
                state['events'] = [dict(name='Sinh hoạt', shift='morning', day=0, period=2)]
                result = cp_scheduler.solve(state, time_limit=10)
                self.assertTrue(result['ok'], result)
                self.assertEqual(sorted(x['period'] for x in result['schedule'] if x['teacher']), [1, 3])

    def test_subject_aliases_share_weekly_total(self):
        state = self.fixture(subject='Lý', periods=1, session_rule='3')
        state['assignments'] += [dict(className='9/1', teacher='Lan', subject=s, periods=1) for s in ('Ly', 'Ly\u0301')]
        state['assignments'].append(dict(className='9/1', teacher='Lan', subject='Toán', periods=3))
        state['schedule'] = [dict(className='9/1', teacher='Lan', subject=s, shift='morning', day=d, period=1, locked=True)
                             for d, s in enumerate(('Lý', 'Ly', 'Ly\u0301'))]
        self.assertTrue(cp_scheduler.solve(state, time_limit=10)['ok'])

    def test_period_count_must_be_an_integer(self):
        for value in (2.5, '2.5', 0, 31, True, None, float('nan'), float('inf')):
            with self.subTest(periods=value):
                with self.assertRaisesRegex(ValueError, 'số nguyên'):
                    cp_scheduler.solve(self.fixture(subject='Văn', periods=value, session_rule='1'), time_limit=10)
        for value in (2, 2.0, '2'):
            self.assertTrue(cp_scheduler.solve(self.fixture(subject='Văn', periods=value, session_rule='1'), time_limit=10)['ok'])

    def test_one_lesson_sessions_are_infeasible(self):
        result = cp_scheduler.solve(self.fixture(), time_limit=10)
        self.assertEqual(result['status'], 'infeasible')
        self.assertIn('ít nhất 2 tiết', result['message'])

    def test_proven_infeasible(self):
        result = cp_scheduler.solve(self.fixture(periods=3, session_rule='1'), time_limit=10)
        self.assertEqual(result['status'], 'infeasible')

    def test_time_off_and_locked_lesson(self):
        state = self.fixture()
        state['assignments'].append(dict(className='9/1', teacher='Lan', subject='Sử', periods=2))
        state['teachers'][0]['offRule'] = 'first'
        lock = {'className': '9/1', 'teacher': 'Lan', 'subject': 'Toán',
                'shift': 'morning', 'day': 2, 'period': 2, 'locked': True}
        state['schedule'] = [lock]
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        self.assertIn(lock, result['schedule'])
        self.assertTrue(all(x['period'] != 1 for x in result['schedule']))

    def test_two_opposite_shift_subject_pairs(self):
        state = {'classes': [{'name': '9/1', 'shift': 'morning'}],
                 'teachers': [{'name': 'Lan', 'sessionRule': '1'},
                              {'name': 'Minh', 'sessionRule': '1'}],
                 'assignments': [{'className': '9/1', 'teacher': 'Lan', 'subject': 'Thể dục', 'periods': 2},
                                 {'className': '9/1', 'teacher': 'Minh', 'subject': 'Hoạt động trải nghiệm', 'periods': 2}],
                 'events': [], 'schedule': []}
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        self.assertEqual({x['shift'] for x in result['schedule']}, {'afternoon'})
        self.assertEqual({x['day'] for x in result['schedule']}, {result['schedule'][0]['day']})
        self.assertEqual({x['period'] for x in result['schedule']}, {1, 2, 3, 4})

    def test_english_across_shifts_needs_eight_sessions(self):
        state = {'classes': [{'name': '9/1', 'shift': 'morning'}, {'name': '8/2', 'shift': 'afternoon'}],
                 'teachers': [{'name': 'Lan'}],
                 'assignments': [{'className': '9/1', 'teacher': 'Lan', 'subject': 'Anh', 'periods': 4},
                                 {'className': '8/2', 'teacher': 'Lan', 'subject': 'Anh', 'periods': 4}],
                 'events': [], 'schedule': []}
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertEqual(result['status'], 'infeasible')
        self.assertIn('4 buổi sáng + 4 buổi chiều', result['message'])

    def test_two_nonadjacent_math_lessons_in_one_session(self):
        state = self.fixture(session_rule='1')
        state['events'] = [dict(name='Sinh hoạt', shift='morning', day=0, period=2)]
        state['schedule'] = [dict(className='9/1', teacher='Lan', subject='Toán', shift='morning', day=0, period=p, locked=True) for p in (1, 3)]
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['singleMath'])
        self.assertEqual({item['period'] for item in result['schedule'] if item['teacher']}, {1, 3})
        state['schedule'][1]['period'] = 2
        self.assertEqual(cp_scheduler.solve(state, time_limit=10)['status'], 'infeasible')

    def experience_fixture(self):
        return {'classes': [{'name': '6/1', 'shift': 'morning'}, {'name': '6/2', 'shift': 'morning'}],
                'teachers': [{'name': 'Lan', 'sessionRule': '1'}, {'name': 'Minh', 'sessionRule': '1'}, {'name': 'An', 'sessionRule': '1'}],
                'assignments': [
                    {'className': c, 'teacher': teacher, 'subject': subject, 'periods': 2}
                    for c, teacher, subject in [('6/1','Lan','Hoạt động trải nghiệm'), ('6/2','Lan','Hoạt động trải nghiệm'),
                                                ('6/1','Minh','Thể dục'), ('6/2','An','Thể dục')]],
                'events': [], 'schedule': []}

    def test_experience_classes_are_paired(self):
        result = cp_scheduler.solve(self.experience_fixture(), time_limit=10)
        self.assertTrue(result['ok'], result)
        lessons = [x for x in result['schedule'] if x['teacher'] == 'Lan']
        self.assertEqual(len({(x['day'], x['shift']) for x in lessons}), 1)
        self.assertTrue(result['pairedExperience'])

    def test_experience_pairing_respects_locked_lessons(self):
        state = self.experience_fixture()
        state['teachers'][0]['sessionRule'] = '2'
        state['schedule'] = [dict(className=c, teacher='Lan', subject='Hoạt động trải nghiệm',
                                  shift='afternoon', day=d, period=p, locked=True)
                             for c, d in [('6/1', 0), ('6/2', 1)] for p in (1, 2)]
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['pairedExperience'])
        self.assertEqual(cp_scheduler.solve(state, time_limit=10, require_extra_pairing=True)['status'], 'infeasible')

    def test_infeasible_pair_does_not_prevent_other_pairs(self):
        state = self.experience_fixture()
        state['teachers'][0]['sessionRule'] = '2'
        state['classes'] += [{'name': '6/3', 'shift': 'morning'}, {'name': '6/4', 'shift': 'morning'}]
        state['teachers'] += [{'name': 'Hoa', 'sessionRule': '1'}, {'name': 'Gym3', 'sessionRule': '1'}, {'name': 'Gym4', 'sessionRule': '1'}]
        state['assignments'] += [dict(className=c, teacher=t, subject=s, periods=2) for c,t,s in [
            ('6/3','Hoa','Hoạt động trải nghiệm'),('6/4','Hoa','Hoạt động trải nghiệm'),
            ('6/3','Gym3','Thể dục'),('6/4','Gym4','Thể dục')]]
        state['schedule'] = [dict(className=c, teacher='Lan', subject='Hoạt động trải nghiệm', shift='afternoon',
                                  day=d, period=p, locked=True)
                             for c, d in [('6/1', 0), ('6/2', 1)] for p in (1, 2)]
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['pairedExperience'])
        hoa = [x for x in result['schedule'] if x['teacher'] == 'Hoa']
        self.assertEqual(len({(x['shift'], x['day']) for x in hoa}), 1)
        self.assertIn('Lan (chiều)', result['unpairedExperience'])

    def test_unknown_preference_falls_back_to_full_search(self):
        from ortools.sat.python import cp_model
        class UnknownSolver:
            def __init__(self):
                self.parameters = type('Parameters', (), {})()
            def solve(self, model):
                return cp_model.UNKNOWN
        state = self.fixture(subject='Van', periods=4, session_rule='2')
        real_solver = cp_model.CpSolver()
        with patch('ortools.sat.python.cp_model.CpSolver', side_effect=[UnknownSolver(), real_solver]) as factory:
            result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        self.assertEqual(factory.call_count, 2)

    def test_unknown_full_search_is_not_infeasible(self):
        from ortools.sat.python import cp_model
        class UnknownSolver:
            def __init__(self):
                self.parameters = type('Parameters', (), {})()
            def solve(self, model):
                return cp_model.UNKNOWN
        with patch('ortools.sat.python.cp_model.CpSolver', side_effect=UnknownSolver) as factory:
            result = cp_scheduler.solve(self.fixture(subject='Van', periods=4, session_rule='2'), time_limit=10)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(factory.call_count, 2)

    def test_reports_teacher_with_too_few_periods(self):
        state = self.fixture(subject='Van', periods=4, session_rule='4')
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertEqual(result['status'], 'infeasible')
        self.assertIn('Lan', result['message'])
        self.assertIn('4', result['message'])

    def test_literature_pairs_on_consecutive_days(self):
        state = self.fixture(subject='Ngữ văn', periods=4, session_rule='2')
        state['schedule'] = [dict(className='9/1', teacher='Lan', subject='Ngữ văn', shift='morning', day=d, period=p, locked=True) for d in (0, 1) for p in (1, 2)]
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        days = {}
        for lesson in result['schedule']:
            days.setdefault(lesson['day'], []).append(lesson['period'])
        self.assertEqual(len(days), 2)
        for periods in days.values():
            self.assertEqual(len(periods), 2)
            self.assertEqual(abs(periods[0]-periods[1]), 1)
        self.assertEqual(sorted(days), [0, 1])

    def test_literature_odd_lesson(self):
        state = self.fixture(subject='Văn', periods=5, session_rule='3')
        state['assignments'].append(dict(className='9/1', teacher='Lan', subject='Sử', periods=1))
        result = cp_scheduler.solve(state, time_limit=10)
        self.assertTrue(result['ok'], result)
        counts = {}
        for lesson in result['schedule']:
            if lesson['subject'] != 'Văn':
                continue
            counts[lesson['day']] = counts.get(lesson['day'], 0) + 1
        self.assertEqual(sorted(counts.values()), [1, 2, 2])
        self.assertEqual(len(counts), 3)


if __name__ == '__main__':
    unittest.main()
