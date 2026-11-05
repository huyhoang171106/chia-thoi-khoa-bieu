"""Independent check that a timetable obeys every scheduling rule.

Sessions are numbered 0-4 for Monday-Friday mornings and 6-10 for the
afternoons; periods are numbered 0-4.
"""
import re
from collections import Counter

from .solver import extra_kind, period_count, subject_group, subject_key
from .state import number, rows, teacher_key, text

EMPTY = -1


class RuleError(ValueError):
    pass


def min_sessions(teacher):
    rule = text(teacher, 'sessionRule')
    if rule in ('', 'standard'):
        return 4
    if re.fullmatch('[1-6]', rule):
        return int(rule)
    raise RuleError('Số buổi dạy riêng của giáo viên không hợp lệ.')


def max_sessions(teacher):
    return 5 if text(teacher, 'sessionRule') in ('', 'standard') else min_sessions(teacher)


def unavailable(teacher, session, period):
    rule = text(teacher, 'offRule')
    if rule in ('', 'standard'):
        return False
    if rule == 'first':
        return period == 0
    if re.fullmatch('day:[0-4]', rule):
        return session % 6 == int(rule[4])
    if re.fullmatch('session:[0-4]:(morning|afternoon)', rule):
        _, day, shift = rule.split(':')
        return session % 6 == int(day) and (session < 6) == (shift == 'morning')
    raise RuleError('Thời gian nghỉ của giáo viên không hợp lệ.')


def offset(shift):
    return 0 if shift == 'morning' else 6


def opposite(shift):
    return 'afternoon' if shift == 'morning' else 'morning'


def validate(state):
    """Check a timetable in which every lesson is locked; return its slots."""
    classes, teachers = rows(state, 'classes'), rows(state, 'teachers')
    assignments, events = rows(state, 'assignments'), rows(state, 'events')
    if not classes or not teachers or not assignments:
        raise RuleError('Hãy nhập lớp, giáo viên và phân công trước khi xếp lịch.')

    teacher_index, keys = {}, set()
    for i, teacher in enumerate(teachers):
        name = text(teacher, 'name')
        if not name or teacher_key(name) in keys:
            raise RuleError('Tên giáo viên không được trống hoặc trùng.')
        keys.add(teacher_key(name))
        min_sessions(teacher)
        unavailable(teacher, 0, 0)
        teacher_index[name] = i

    class_index, class_names, class_shifts = {}, [], []
    for i, klass in enumerate(classes):
        name, shift = text(klass, 'name'), text(klass, 'shift')
        if not name or name in class_index or shift not in ('morning', 'afternoon'):
            raise RuleError('Kiểm tra tên lớp và buổi học; tên lớp không được trùng.')
        class_index[name] = i
        class_names.append(name)
        class_shifts.append(shift)

    # Per-assignment facts, computed once.
    owner, teacher_of, subject, group, periods, kind = [], [], [], [], [], []
    for a in assignments:
        if text(a, 'className') not in class_index or text(a, 'teacher') not in teacher_index or not text(a, 'subject'):
            raise RuleError('Kiểm tra phân công: lớp, giáo viên, môn và số tiết từ 1 đến 30.')
        try:
            periods.append(period_count(a))
        except ValueError as error:
            raise RuleError(str(error)) from None
        owner.append(class_index[text(a, 'className')])
        teacher_of.append(teacher_index[text(a, 'teacher')])
        subject.append(text(a, 'subject'))
        group.append(subject_group(subject[-1]))
        kind.append(extra_kind(subject[-1]))
    key = [subject_key(name) for name in subject]
    literature = [k in ('van', 'nguvan') for k in key]
    flexible = [k in ('toan', 'anh', 'tienganh') for k in key]
    group_total = Counter()
    for ai in range(len(assignments)):
        group_total[owner[ai], group[ai]] += periods[ai]

    for t, teacher in enumerate(teachers):
        name = text(teacher, 'name')
        total = sum(periods[ai] for ai in range(len(assignments)) if teacher_of[ai] == t)
        if 0 < total < 2 * min_sessions(teacher):
            raise RuleError(f'Giáo viên {name} chỉ có {total} tiết phân công, không đủ để dạy ít nhất 2 tiết '
                            f'mỗi buổi trong {min_sessions(teacher)} buổi/tuần.')
        if total > max_sessions(teacher) * 5:
            raise RuleError(f'Giáo viên {name} có {total} tiết, vượt sức chứa tối đa của '
                            f'{max_sessions(teacher)} buổi/tuần.')

    extras = [[-1, -1] for _ in classes]
    for ai in range(len(assignments)):
        if kind[ai]:
            if extras[owner[ai]][kind[ai] - 1] >= 0 or periods[ai] != 2:
                raise RuleError('Mỗi lớp cần một phân công 2 tiết cho mỗi môn Hoạt động trải nghiệm và Thể dục.')
            extras[owner[ai]][kind[ai] - 1] = ai
    if any(kind):
        for c, pair in enumerate(extras):
            if min(pair) < 0:
                raise RuleError(f'Lớp {class_names[c]} cần phân công đủ 2 tiết Hoạt động trải nghiệm và 2 tiết Thể dục.')

    for event in events:
        if not (0 <= number(event, 'day', -1) <= 4 and 1 <= number(event, 'period', 0) <= 5 and text(event, 'name')
                and text(event, 'shift') in ('morning', 'afternoon')):
            raise RuleError('Hoạt động cố định chỉ được xếp từ thứ Hai đến thứ Sáu, tiết 1–5.')

    # grid holds an assignment index, EMPTY, or -10 - event index.
    grid = [[[EMPTY] * 5 for _ in range(12)] for _ in classes]
    busy = [[[False] * 5 for _ in range(12)] for _ in teachers]
    load = [[0] * 12 for _ in teachers]
    for ei, event in enumerate(events):
        session = number(event, 'day', -1) + offset(text(event, 'shift'))
        p = number(event, 'period', 0) - 1
        for c in range(len(classes)):
            if class_shifts[c] == text(event, 'shift'):
                if grid[c][session][p] != EMPTY:
                    raise RuleError('Hai hoạt động cố định đang trùng cùng một tiết.')
                grid[c][session][p] = -10 - ei

    def lesson_shift(ai):
        main = class_shifts[owner[ai]]
        return opposite(main) if kind[ai] else main

    candidates = {}
    for ai, a in enumerate(assignments):
        candidates.setdefault((text(a, 'className'), text(a, 'teacher'), text(a, 'subject')), []).append(ai)
    used = [0] * len(assignments)
    for lock in rows(state, 'schedule'):
        if lock.get('locked') is not True or number(lock, 'day', -1) == 5:
            continue
        cname, teacher, name, shift = (text(lock, k) for k in ('className', 'teacher', 'subject', 'shift'))
        c, d, p = class_index.get(cname, -1), number(lock, 'day', -1), number(lock, 'period', 0) - 1
        if c < 0 or not 0 <= d <= 4 or not 0 <= p <= 4 or teacher not in teacher_index:
            raise RuleError('Có tiết khóa không hợp lệ. Hãy kiểm tra lớp, giáo viên và thời gian.')
        ai = next((i for i in candidates.get((cname, teacher, name), []) if used[i] < periods[i]), -1)
        if ai < 0 or lesson_shift(ai) != shift:
            raise RuleError(f'Tiết khóa không khớp phân công hoặc buổi học: {name} · {cname}')
        t, session = teacher_index[teacher], d + offset(shift)
        if unavailable(teachers[t], session, p):
            raise RuleError(f'Tiết khóa trùng thời gian nghỉ của giáo viên {teacher}.')
        if grid[c][session][p] != EMPTY or busy[t][session][p]:
            raise RuleError('Tiết khóa bị trùng lớp, giáo viên hoặc hoạt động cố định.')
        grid[c][session][p] = ai
        busy[t][session][p] = True
        load[t][session] += 1
        used[ai] += 1

    def lessons(c, session):
        return [(p, ai) for p, ai in enumerate(grid[c][session]) if ai >= 0]

    for c in range(len(classes)):
        for session in range(12):
            math = sum(key[ai] == 'toan' for _, ai in lessons(c, session))
            english = sum(key[ai] in ('anh', 'tienganh') for _, ai in lessons(c, session))
            if math > 2 or english > 1:
                raise RuleError(f'Các tiết khóa của lớp {class_names[c]} vượt số tiết Toán hoặc Anh trong cùng một buổi.')

    def literature_error(c, complete):
        name, main = class_names[c], offset(class_shifts[c])
        total = sum(periods[ai] for ai in range(len(assignments)) if owner[ai] == c and literature[ai])
        singles = 0
        for day in range(5):
            found = [p for p, ai in lessons(c, main + day) if literature[ai]]
            if len(found) > 2:
                return f'Lớp {name} chỉ được học tối đa 2 tiết Văn trong một buổi.'
            if len(found) == 2 and found[1] - found[0] != 1:
                return f'Hai tiết Văn của lớp {name} trong cùng buổi phải liền nhau.'
            singles += len(found) == 1
        if complete and total > 0 and singles != total % 2:
            return (f'Các tiết Văn của lớp {name} phải ghép thành từng cặp liền nhau; '
                    'chỉ được một tiết lẻ nếu số tiết tuần là số lẻ.')
        return ''

    for c in range(len(classes)):
        error = literature_error(c, False)
        if error:
            raise RuleError(error)
    for t, teacher in enumerate(teachers):
        if sum(n > 0 for n in load[t]) > max_sessions(teacher):
            raise RuleError(f'Các tiết khóa khiến giáo viên {text(teacher, "name")} vượt số buổi đã chọn.')

    for c in range(len(classes)):
        main = offset(class_shifts[c])
        cells = [(d, p, grid[c][main + d][p]) for d in range(5) for p in range(5)]
        for i, (d, p, a) in enumerate(cells):
            if a < 0:
                continue
            for dd, q, b in cells[i + 1:]:
                if b < 0 or group[b] != group[a]:
                    continue
                adjacent = d == dd and q - p == 1
                if adjacent and not literature[a]:
                    raise RuleError(f'Chỉ môn Văn được xếp tiết đôi trong buổi chính: {subject[a]}.')
                if not literature[a] and group_total[c, group[a]] < 3 and not flexible[a] and dd - d < 2:
                    single = d == dd and teacher_of[a] == teacher_of[b] and max_sessions(teachers[teacher_of[a]]) == 1
                    if not single:
                        raise RuleError(f'Các tiết khóa của môn {subject[a]} cần cách nhau ít nhất 1 ngày ở giữa.')
    for c in range(len(classes)):
        for d in range(5):
            row = grid[c][offset(class_shifts[c]) + d]
            for p in range(3):
                a, b, z = row[p:p + 3]
                if min(a, b, z) >= 0 and literature[a] and group[a] == group[b] == group[z]:
                    raise RuleError('Môn Văn chỉ được xếp tối đa 2 tiết liên tiếp.')

    if used != periods:
        raise RuleError('Kết quả xếp lịch không đủ hoặc thừa tiết so với phân công.')

    for c, (first, second) in enumerate(extras):
        if first < 0:
            continue
        placed = sorted((session, p, ai) for session in range(12) for p, ai in lessons(c, session) if kind[ai])
        sessions = {session for session, _, _ in placed}
        order = [ai for _, _, ai in placed]
        if (len(sessions) != 1 or [p for _, p, _ in placed] != [0, 1, 2, 3]
                or order not in ([first, first, second, second], [second, second, first, first])):
            raise RuleError(f'Lớp {class_names[c]} cần học Hoạt động trải nghiệm và Thể dục trong cùng một buổi '
                            'trái buổi, mỗi môn 2 tiết liền nhau ở tiết 1–4.')

    for c in range(len(classes)):
        error = literature_error(c, True)
        if error:
            raise RuleError(error)
        for session in range(12):
            filled = [p for p in range(5) if grid[c][session][p] != EMPTY]
            if filled and len(filled) != filled[-1] - filled[0] + 1:
                raise RuleError(f'Lớp {class_names[c]} có tiết trống xen giữa các tiết trong một buổi.')
    for t, teacher in enumerate(teachers):
        name, sessions = text(teacher, 'name'), 0
        for session in range(12):
            taught = [p for p in range(5) if busy[t][session][p]]
            if not taught:
                continue
            if any(later - earlier > 2 for earlier, later in zip(taught, taught[1:])):
                raise RuleError(f'Giáo viên {name} có hơn 1 tiết trống liên tiếp trong một buổi.')
            if len(taught) < 2:
                raise RuleError(f'Giáo viên {name} có buổi dạy chỉ 1 tiết.')
            sessions += 1
        if sessions and not min_sessions(teacher) <= sessions <= max_sessions(teacher):
            raise RuleError(f'Giáo viên {name} dạy {sessions} buổi, ngoài số buổi đã chọn.')

    slots = set()
    for c in range(len(classes)):
        for session in range(12):
            shift = 'morning' if session < 6 else 'afternoon'
            for p, cell in enumerate(grid[c][session]):
                if cell >= 0:
                    a = assignments[cell]
                    slots.add((class_names[c], shift, session % 6, p + 1, text(a, 'subject'), text(a, 'teacher')))
                elif cell != EMPTY:
                    slots.add((class_names[c], shift, session % 6, p + 1, text(events[-10 - cell], 'name'), ''))
    return slots


def slot(lesson):
    return (text(lesson, 'className'), text(lesson, 'shift'), number(lesson, 'day', -1),
            number(lesson, 'period', 0), text(lesson, 'subject'), text(lesson, 'teacher'))


def check_result(state, result):
    """Reject a solver result unless it matches the assignments and every rule."""
    expected, actual = Counter(), Counter()
    for a in rows(state, 'assignments'):
        expected[text(a, 'className'), text(a, 'teacher'), text(a, 'subject')] += period_count(a)
    schedule = rows(result, 'schedule')
    for lesson in schedule:
        if text(lesson, 'teacher'):
            actual[text(lesson, 'className'), text(lesson, 'teacher'), text(lesson, 'subject')] += 1
    if expected != actual:
        raise ValueError('Kết quả xếp lịch không đủ hoặc thừa tiết so với phân công.')
    locks = [dict(lesson, locked=True) for lesson in schedule if text(lesson, 'teacher')]
    try:
        verified = validate(dict(state, schedule=locks))
    except RuleError as error:
        raise ValueError(f'Kết quả không vượt qua bước kiểm tra quy định: {error}') from None
    placed = {slot(lesson) for lesson in schedule}
    if len(placed) != len(schedule) or placed != verified:
        raise ValueError('Kết quả không khớp hoạt động cố định hoặc tiết đã xếp.')
    for old in rows(state, 'schedule'):
        if old.get('locked') is True and number(old, 'day', -1) != 5 and slot(old) not in placed:
            raise ValueError('Kết quả không giữ nguyên tiết đã khóa.')
