"""Field access and checks for the application state document."""
import json
import re
import unicodedata

# Java's String.trim() removes every character up to and including the space.
_TRIM = ''.join(map(chr, range(33)))


def rows(document, key):
    value = document.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError('Dữ liệu không hợp lệ.')
    return value


def text(row, key):
    value = row.get(key)
    if value is None:
        return ''
    if isinstance(value, bool):
        value = 'true' if value else 'false'
    return str(value).strip(_TRIM)


def number(row, key, default):
    value = row.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return default
    if isinstance(value, str) and re.fullmatch(r'[+-]?[0-9]+', value):
        return int(value)
    return default


def teacher_key(name):
    return unicodedata.normalize('NFC', ' '.join(name.split())).lower()


def parse(body):
    try:
        return json.loads(body)
    except ValueError:
        raise ValueError('JSON không hợp lệ') from None


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def clean(body):
    """Parse a stored or uploaded state document and drop retired fields."""
    state = parse(body)
    if not isinstance(state, dict):
        raise ValueError('Dữ liệu không hợp lệ.')
    state.pop('closed', None)
    return state


def check_teacher_names(state):
    teachers = state.get('teachers')
    if not isinstance(teachers, list):
        return
    seen = set()
    for teacher in teachers:
        if not isinstance(teacher, dict):
            raise ValueError('Dữ liệu giáo viên không hợp lệ.')
        name = teacher.get('name')
        name = '' if name is None else str(name)
        key = teacher_key(name)
        if key and key in seen:
            raise ValueError(f'Tên giáo viên bị trùng: {name.strip()}. Hãy giữ một giáo viên duy nhất.')
        seen.add(key)
