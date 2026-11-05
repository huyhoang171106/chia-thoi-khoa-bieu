"""CP-SAT timetable solver. Reads a state JSON document from stdin."""
import json
import time
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build' / 'vendor'))


def subject_key(text):
    text = unicodedata.normalize('NFD', str(text).lower().replace('đ', 'd'))
    return ''.join(c for c in text if c.isascii() and c.isalnum())


def extra_kind(subject):
    return {'hoatdongtrainghiem': 1, 'theduc': 2}.get(subject_key(subject), 0)


def session_conflicts(classes, teachers, assignments, single_math=False):
    """Return necessary lower bounds; never treat these as a full feasibility test."""
    class_by_name = {c['name']: c for c in classes}
    conflicts = []
    for teacher in teachers:
        teacher_assignments = [a for a in assignments if a.get('teacher') == teacher['name']]
        per_shift = defaultdict(int)
        per_class_subject = defaultdict(int)
        extra_periods = defaultdict(int)
        for a in teacher_assignments:
            c = class_by_name.get(a.get('className'))
            if not c:
                continue
            kind = extra_kind(a.get('subject', ''))
            shift = c['shift']
            if kind:
                shift = 'afternoon' if shift == 'morning' else 'morning'
            periods = int(a.get('periods', 0))
            per_shift[shift] += periods
            if kind:
                extra_periods[shift] += periods
            key = subject_key(a.get('subject', ''))
            if key in ('toan', 'anh', 'tienganh'):
                per_class_subject[shift, a['className'], 'anh' if key != 'toan' else key] += periods
        required = {}
        for shift, periods in per_shift.items():
            capacity = 4 if teacher.get('offRule') == 'first' else 5
            limits = [(periods + capacity - 1) // capacity, (extra_periods[shift] + 3) // 4]
            limits += [(n + 1) // 2 if subject == 'toan' and not single_math else n
                       for (sh, _, subject), n in per_class_subject.items() if sh == shift]
            required[shift] = max(limits)
        rule = str(teacher.get('sessionRule') or 'standard')
        maximum = 5 if rule == 'standard' else int(rule)
        if sum(required.values()) > maximum:
            conflicts.append((teacher['name'], required.get('morning', 0), required.get('afternoon', 0), maximum))
    return conflicts


def solve(state, time_limit=None, require_extra_pairing=False):
    from ortools.sat.python import cp_model

    classes = state.get('classes', [])
    teachers = state.get('teachers', [])
    assignments = state.get('assignments', [])
    events = state.get('events', [])
    if not classes or not teachers or not assignments:
        raise ValueError('Hãy nhập lớp, giáo viên và phân công trước khi xếp lịch.')
    class_by_name = {c['name']: c for c in classes}
    teacher_by_name = {t['name']: t for t in teachers}
    if len(class_by_name) != len(classes) or len(teacher_by_name) != len(teachers):
        raise ValueError('Tên lớp hoặc giáo viên bị trùng.')
    conflicts = session_conflicts(classes, teachers, assignments)
    if conflicts:
        details = '; '.join(f'{name}: ít nhất {morning} buổi sáng + {afternoon} buổi chiều, tối đa {maximum} buổi'
                            for name, morning, afternoon, maximum in conflicts)
        return {'ok': False, 'status': 'infeasible', 'message':
                'Số buổi theo phân công vượt giới hạn: ' + details + '. Hãy điều chỉnh số buổi hoặc phân công.'}
    single_math_conflicts = session_conflicts(classes, teachers, assignments, single_math=True)
    model = cp_model.CpModel()
    variables = {}
    by_class = defaultdict(list)
    by_teacher = defaultdict(list)
    by_subject = defaultdict(list)
    extras = defaultdict(dict)
    soft_costs = []
    shifts = ('morning', 'afternoon')

    def allowed(teacher, shift, day, period):
        rule = str(teacher.get('offRule') or 'standard').split(':')
        return not (rule[0] == 'first' and period == 1 or
                    rule[0] == 'day' and int(rule[1]) == day or
                    rule[0] == 'session' and int(rule[1]) == day and rule[2] == shift)

    for ai, assignment in enumerate(assignments):
        cname, tname = assignment.get('className'), assignment.get('teacher')
        subject = assignment.get('subject', '')
        if cname not in class_by_name or tname not in teacher_by_name or not subject:
            raise ValueError('Kiểm tra lớp, giáo viên và môn trong phân công.')
        periods = int(assignment.get('periods', 0))
        if not 1 <= periods <= 30:
            raise ValueError('Số tiết trong phân công phải từ 1 đến 30.')
        kind = extra_kind(subject)
        main_shift = class_by_name[cname]['shift']
        shift = shifts[1 - shifts.index(main_shift)] if kind else main_shift
        if kind:
            if kind in extras[cname] or periods != 2:
                raise ValueError('Mỗi lớp cần một phân công 2 tiết cho mỗi môn trái buổi.')
            extras[cname][kind] = ai
        choices = []
        for day in range(5):
            for period in range(1, 6):
                if not allowed(teacher_by_name[tname], shift, day, period):
                    continue
                var = model.new_bool_var(f'a{ai}_d{day}_p{period}')
                variables[ai, day, period] = var
                choices.append(var)
                by_class[cname, shift, day, period].append(var)
                by_teacher[tname, shift, day, period].append(var)
                if not kind:
                    group = 'van' if subject_key(subject) in ('van', 'nguvan') else subject.strip().lower()
                    by_subject[cname, group].append((ai, day, period, var))
        model.add(sum(choices) == periods)
    if extras and any(set(extras[c['name']]) != {1, 2} for c in classes):
        raise ValueError('Mỗi lớp cần đủ Hoạt động trải nghiệm và Thể dục.')

    # Necessary capacity check for the two-period minimum per teaching session.
    for teacher in teachers:
        periods_by_shift = defaultdict(int)
        for assignment in assignments:
            if assignment.get('teacher') != teacher['name']:
                continue
            shift = class_by_name[assignment['className']]['shift']
            if extra_kind(assignment['subject']):
                shift = shifts[1 - shifts.index(shift)]
            periods_by_shift[shift] += int(assignment['periods'])
        total = sum(periods_by_shift.values())
        rule = str(teacher.get('sessionRule') or 'standard')
        minimum = 4 if rule == 'standard' else int(rule)
        if total and sum(count // 2 for count in periods_by_shift.values()) < minimum:
            return {'ok': False, 'status': 'infeasible', 'message':
                    f"Gi\u00e1o vi\u00ean {teacher['name']} c\u00f3 {total} ti\u1ebft ph\u00e2n c\u00f4ng, kh\u00f4ng \u0111\u1ee7 \u0111\u1ec3 d\u1ea1y {minimum} bu\u1ed5i m\u1ed7i bu\u1ed5i \u00edt nh\u1ea5t 2 ti\u1ebft. H\u00e3y \u0111i\u1ec1u ch\u1ec9nh s\u1ed1 bu\u1ed5i ho\u1eb7c ph\u00e2n c\u00f4ng."}

    fixed = set()
    for event in events:
        day, period, shift = int(event['day']), int(event['period']), event['shift']
        if day not in range(5) or period not in range(1, 6) or shift not in shifts or not event.get('name'):
            raise ValueError('Hoạt động cố định không hợp lệ.')
        for c in classes:
            if c['shift'] == shift:
                key = c['name'], shift, day, period
                if key in fixed:
                    raise ValueError('Các hoạt động cố định bị trùng.')
                fixed.add(key)

    for c in classes:
        cname = c['name']
        for shift in shifts:
            for day in range(5):
                occupied = []
                for period in range(1, 6):
                    key = cname, shift, day, period
                    slot = sum(by_class[key]) + int(key in fixed)
                    model.add(slot <= 1)
                    occupied.append(slot)
                for left in range(5):
                    for right in range(left + 2, 5):
                        for mid in range(left + 1, right):
                            model.add(occupied[left] + occupied[right] - 1 <= occupied[mid])

    for t in teachers:
        tname = t['name']
        sessions = []
        for shift in shifts:
            for day in range(5):
                busy = [sum(by_teacher[tname, shift, day, p]) for p in range(1, 6)]
                for slot in busy:
                    model.add(slot <= 1)
                session = model.new_bool_var(f'session_{len(sessions)}_{tname}')
                model.add(sum(busy) >= 2 * session)
                model.add(sum(busy) <= 5 * session)
                sessions.append(session)
                for left in range(5):
                    for right in range(left + 3, 5):
                        model.add(sum(busy[left + 1:right]) >= busy[left] + busy[right] - 1)
                # Prefer compact teaching sessions, while still accepting every
                # timetable that meets the hard gap and session rules above.
                for period in range(1, 4):
                    gap = model.new_bool_var(f'gap_{tname}_{shift}_{day}_{period}')
                    for left in range(period):
                        for right in range(period + 1, 5):
                            model.add(gap >= busy[left] + busy[right] - busy[period] - 1)
                    soft_costs.append(20 * gap)
                shortfall = model.new_int_var(0, 3, f'short_{tname}_{shift}_{day}')
                model.add(shortfall >= 3 * session - sum(busy))
                soft_costs.append(4 * shortfall)
                long_session = model.new_bool_var(f'long_{tname}_{shift}_{day}')
                model.add(sum(busy) <= 4 + long_session)
                soft_costs.append(8 * long_session)
        rule = str(t.get('sessionRule') or 'standard')
        minimum, maximum = (4, 5) if rule == 'standard' else (int(rule), int(rule))
        has_assignments = any(a['teacher'] == tname for a in assignments)
        if has_assignments:
            model.add(sum(sessions) >= minimum)
            model.add(sum(sessions) <= maximum)

    for cname, pair in extras.items():
        options = []
        for day in range(5):
            for order in ((1, 2), (2, 1)):
                chosen = model.new_bool_var(f'extra_{cname}_{day}_{order[0]}')
                options.append(chosen)
                for p in range(1, 5):
                    ai = pair[order[0] if p <= 2 else order[1]]
                    var = variables.get((ai, day, p))
                    if var is None:
                        model.add(chosen == 0)
                    else:
                        model.add(var == 1).only_enforce_if(chosen)
        model.add_exactly_one(options)

    limited = defaultdict(list)
    for (cname, subject), rows in by_subject.items():
        key = subject_key(subject)
        is_literature = key in ('van', 'nguvan')
        subject_total = sum(int(a['periods']) for a in assignments if a['className'] == cname and
                            (subject_key(a['subject']) in ('van', 'nguvan') if is_literature
                             else a['subject'].strip().lower() == subject))
        flexible = key in ('toan', 'anh', 'tienganh')
        for ai, day, period, var in rows:
            if flexible:
                limited[cname, 'anh' if key in ('anh', 'tienganh') else key, day].append(var)
        for i, (ai, d1, p1, v1) in enumerate(rows):
            for aj, d2, p2, v2 in rows[i + 1:]:
                adjacent = d1 == d2 and abs(p1 - p2) == 1
                same_teacher = assignments[ai]['teacher'] == assignments[aj]['teacher']
                teacher_rule = str(teacher_by_name[assignments[ai]['teacher']].get('sessionRule') or 'standard')
                single_session = d1 == d2 and same_teacher and teacher_rule == '1'
                if not is_literature and (adjacent or (subject_total < 3 and not flexible and
                    abs(d1 - d2) < 2 and not single_session)):
                    model.add(v1 + v2 <= 1)
        if is_literature:
            single_days = []
            for day in range(5):
                periods = [sum(v for _, d, p, v in rows if d == day and p == period) for period in range(1, 6)]
                pairs = [model.new_bool_var(f'lit_pair_{cname}_{day}_{start}') for start in range(1, 5)]
                single = model.new_bool_var(f'lit_single_{cname}_{day}')
                active = model.new_bool_var(f'lit_day_{cname}_{day}')
                model.add(sum(pairs) + single == active)
                model.add(sum(periods) == 2 * sum(pairs) + single)
                for start, pair in enumerate(pairs):
                    model.add(periods[start] == 1).only_enforce_if(pair)
                    model.add(periods[start + 1] == 1).only_enforce_if(pair)
                single_days.append(single)
            model.add(sum(single_days) == subject_total % 2)
    prefer_single_math = model.new_bool_var('prefer_single_math')
    math_doubles = []
    for (_, subject, _), group in limited.items():
        model.add(sum(group) <= (2 if subject == 'toan' else 1))
        if subject == 'toan':
            model.add(sum(group) <= 1).only_enforce_if(prefer_single_math)
            doubled = model.new_bool_var(f'math_double_{len(math_doubles)}')
            model.add(sum(group) <= 1 + doubled)
            model.add(sum(group) >= 2 * doubled)
            math_doubles.append(doubled)

    # Each experience assignment is a two-period block. Two classes taught by
    # the same teacher can share a session, one in periods 1–2 and one in 3–4.
    experience_groups = defaultdict(list)
    for cname, pair in extras.items():
        ai = pair[1]
        teacher = assignments[ai]['teacher']
        main_shift = class_by_name[cname]['shift']
        shift = shifts[1 - shifts.index(main_shift)]
        experience_groups[teacher, shift].append(ai)
    prefer_paired_experience = model.new_bool_var('prefer_paired_experience')
    pairing_excess = []
    pairing_groups = []
    for (teacher, shift), group in experience_groups.items():
        if len(group) < 2:
            continue
        used_sessions = []
        for day in range(5):
            used = model.new_bool_var(f'experience_{teacher}_{shift}_{day}')
            periods = [variables[ai, day, p] for ai in group for p in range(1, 5)
                       if (ai, day, p) in variables]
            model.add(sum(periods) >= used)
            model.add(sum(periods) <= 4 * used)
            used_sessions.append(used)
        minimum_sessions = (len(group) + 1) // 2
        pair_selected = model.new_bool_var(f'experience_pair_{teacher}_{shift}')
        model.add(pair_selected == 1).only_enforce_if(prefer_paired_experience)
        model.add(sum(used_sessions) <= minimum_sessions).only_enforce_if(pair_selected)
        pairing_groups.append((teacher, shift, pair_selected, used_sessions, minimum_sessions))
        excess = model.new_int_var(0, len(group), f'experience_excess_{teacher}_{shift}')
        model.add(excess >= sum(used_sessions) - minimum_sessions)
        pairing_excess.append(excess)

    locked = set()
    for item in state.get('schedule', []):
        if not item.get('locked') or int(item.get('day', -1)) == 5:
            continue
        cname, tname, subject, shift = (item.get(k) for k in ('className', 'teacher', 'subject', 'shift'))
        day, period = int(item.get('day', -1)), int(item.get('period', 0))
        matching = [variables[ai, day, period] for ai, a in enumerate(assignments)
                    if a['className'] == cname and a['teacher'] == tname and a['subject'] == subject
                    and (ai, day, period) in variables and
                    (shifts[1 - shifts.index(class_by_name[cname]['shift'])] if extra_kind(subject)
                     else class_by_name[cname]['shift']) == shift]
        if not matching:
            raise ValueError('Tiết khóa không khớp phân công hoặc thời gian nghỉ.')
        model.add(sum(matching) == 1)
        locked.add((cname, shift, day, period))

    # A previously generated schedule is a search hint only; unlocked lessons
    # remain free to move and every hard constraint is still enforced.
    hinted = set()
    for item in state.get('schedule', []):
        cname, teacher, subject, shift = (item.get(k) for k in ('className', 'teacher', 'subject', 'shift'))
        if cname not in class_by_name or not teacher:
            continue
        try:
            day, period = int(item.get('day', -1)), int(item.get('period', 0))
        except (ValueError, TypeError):
            continue
        main_shift = class_by_name[cname]['shift']
        expected_shift = shifts[1 - shifts.index(main_shift)] if extra_kind(subject) else main_shift
        if shift != expected_shift:
            continue
        for ai, assignment in enumerate(assignments):
            key = ai, day, period
            if (key in variables and key not in hinted and assignment['className'] == cname and
                assignment['teacher'] == teacher and assignment['subject'] == subject):
                model.add_hint(variables[key], 1)
                hinted.add(key)
                break

    compact_weight = 800 * len(teachers) + 1
    pairing_bound = sum(len(group) for group in experience_groups.values())
    model.minimize(sum(math_doubles) * (pairing_bound + 1) * compact_weight +
                   sum(pairing_excess) * compact_weight + sum(soft_costs))
    # Try preferences briefly, then search the complete model.
    scenarios = [(True, True), (False, require_extra_pairing)]
    started = time.monotonic()
    status = cp_model.UNKNOWN
    solver = None
    for index, (single_math, pair_experience) in enumerate(scenarios):
        if single_math and single_math_conflicts:
            continue
        remaining = None if time_limit is None else time_limit - (time.monotonic() - started)
        if remaining is not None and remaining <= 0:
            status = cp_model.UNKNOWN
            break
        model.clear_assumptions()
        model.add_assumptions([prefer_single_math if single_math else prefer_single_math.Not(),
                               prefer_paired_experience if pair_experience else prefer_paired_experience.Not()])
        solver = cp_model.CpSolver()
        solver.parameters.stop_after_first_solution = True
        if index == 0:
            solver.parameters.max_time_in_seconds = min(8, remaining) if remaining is not None else 8
        elif remaining is not None:
            solver.parameters.max_time_in_seconds = remaining
        solver.parameters.num_search_workers = 8
        status = solver.solve(model)
        if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            break
    if status == cp_model.INFEASIBLE:
        return {'ok': False, 'status': 'infeasible', 'message': 'Các quy định và phân công không thể thỏa đồng thời, bao gồm yêu cầu mỗi buổi dạy ít nhất 2 tiết. Hãy kiểm tra số buổi, phân công và các tiết khóa.'}
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return {'ok': False, 'status': 'unknown', 'message': 'Chưa xác định được lịch hợp lệ hay vô nghiệm.'}
    schedule = []
    for (ai, day, period), var in variables.items():
        if not solver.value(var):
            continue
        a = assignments[ai]
        shift = class_by_name[a['className']]['shift']
        if extra_kind(a['subject']):
            shift = shifts[1 - shifts.index(shift)]
        schedule.append({'className': a['className'], 'shift': shift, 'day': day,
                         'period': period, 'subject': a['subject'], 'teacher': a['teacher'],
                         'locked': (a['className'], shift, day, period) in locked})
    for cname, shift, day, period in fixed:
        event = next(e for e in events if e['shift'] == shift and int(e['day']) == day and int(e['period']) == period)
        schedule.append({'className': cname, 'shift': shift, 'day': day, 'period': period,
                         'subject': event['name'], 'teacher': ''})
    math_sessions = defaultdict(int)
    experience_sessions = defaultdict(lambda: defaultdict(set))
    for lesson in schedule:
        if not lesson.get('teacher'):
            continue
        key = subject_key(lesson['subject'])
        if key == 'toan':
            math_sessions[lesson['className'], lesson['shift'], lesson['day']] += 1
        if key == 'hoatdongtrainghiem':
            experience_sessions[lesson['teacher'], lesson['shift']][lesson['day']].add(lesson['className'])
    math_double_count = sum(count == 2 for count in math_sessions.values())
    split_teachers = []
    for (teacher, shift), days in experience_sessions.items():
        count = sum(len(classes) for classes in days.values())
        if count >= 2 and len(days) > (count + 1) // 2:
            split_teachers.append(f'{teacher} ({"sáng" if shift == "morning" else "chiều"})')
    notes = []
    if math_double_count:
        notes.append(f'l\u1ecbch n\u00e0y c\u00f3 {math_double_count} bu\u1ed5i h\u1ecdc 2 ti\u1ebft To\u00e1n; ch\u01b0a x\u00e1c \u0111\u1ecbnh \u0111\u01b0\u1ee3c c\u00f3 th\u1ec3 gi\u1ea3m th\u00eam hay kh\u00f4ng')
    if split_teachers:
        notes.append('ch\u01b0a gh\u00e9p h\u1ebft c\u00e1c l\u1edbp Ho\u1ea1t \u0111\u1ed9ng tr\u1ea3i nghi\u1ec7m cho ' + ', '.join(split_teachers))
    message = 'Đã tìm được lịch hợp lệ.' + (' Lưu ý: ' + '; '.join(notes) + '.' if notes else '')
    return {'ok': True, 'status': 'feasible', 'schedule': schedule, 'message': message,
            'singleMath': math_double_count == 0, 'pairedExperience': not split_teachers,
            'mathDoubleCount': math_double_count, 'unpairedExperience': split_teachers}


if __name__ == '__main__':
    try:
        result = solve(json.load(sys.stdin))
    except ModuleNotFoundError:
        result = {'ok': False, 'status': 'error', 'message':
                  'Chưa tải được OR-Tools. Hãy chạy: python -m pip install --target build/vendor ortools'}
    except Exception as exc:
        result = {'ok': False, 'status': 'error', 'message': str(exc)}
    print(json.dumps(result, ensure_ascii=False))
