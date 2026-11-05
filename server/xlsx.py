"""Read the first sheet of an uploaded workbook and write the school timetable workbook."""
import functools
import io
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

from .state import number, rows, text

MAX_UNZIPPED = 20_000_000
MAX_ENTRIES = 2000
MAX_ROWS = 10001
MAX_COLUMNS = 100
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


class _NoDoctype(ET.TreeBuilder):
    # A DOCTYPE is the only way to declare entities, so refusing it blocks entity expansion attacks.
    def doctype(self, *args):
        raise ValueError('File Excel không hợp lệ.')


def _xml(data):
    parser = ET.XMLParser(target=_NoDoctype())
    try:
        parser.feed(data)
        return parser.close()
    except ET.ParseError:
        raise ValueError('File Excel không hợp lệ.') from None


def _local(element):
    return element.tag.rpartition('}')[2]


def _all(element, name):
    return [e for e in element.iter() if _local(e) == name]


def _text(element, name):
    return ''.join(''.join(e.itertext()) for e in _all(element, name))


def _unzip(data):
    files, total = {}, 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                parts = []
                with archive.open(info) as entry:
                    while chunk := entry.read(8192):
                        total += len(chunk)
                        if total > MAX_UNZIPPED:
                            raise ValueError('File Excel sau giải nén quá lớn.')
                        parts.append(chunk)
                files[info.filename] = b''.join(parts)
                if len(files) > MAX_ENTRIES:
                    raise ValueError('File Excel có quá nhiều thành phần.')
    except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, EOFError, OSError):
        raise ValueError('File không phải Excel .xlsx hợp lệ.') from None
    return files


def _int(value, message):
    if not re.fullmatch(r'[+-]?[0-9]+', value):
        raise ValueError(message)
    return int(value)


def read(data):
    """Return the first sheet as a list of rows, each a list of cell strings."""
    files = _unzip(data)
    if 'xl/workbook.xml' not in files or 'xl/_rels/workbook.xml.rels' not in files:
        raise ValueError('File không phải Excel .xlsx hợp lệ.')
    sheets = _all(_xml(files['xl/workbook.xml']), 'sheet')
    if not sheets:
        raise ValueError('File không có trang tính.')
    rid = sheets[0].get(f'{{{REL_NS}}}id', '')
    target = None
    for relation in _all(_xml(files['xl/_rels/workbook.xml.rels']), 'Relationship'):
        if relation.get('Id', '') == rid and relation.get('TargetMode', '').lower() != 'external':
            target = relation.get('Target', '')
    if target is None:
        raise ValueError('Không tìm thấy trang tính đầu tiên.')
    path = posixpath.normpath(target[1:] if target.startswith('/') else 'xl/' + target)
    if not path.startswith('xl/') or path not in files:
        raise ValueError('Không đọc được trang tính đầu tiên.')

    shared = []
    if 'xl/sharedStrings.xml' in files:
        shared = [_text(si, 't') for si in _all(_xml(files['xl/sharedStrings.xml']), 'si')]

    sheet_rows = _all(_xml(files[path]), 'row')
    if len(sheet_rows) > MAX_ROWS:
        raise ValueError('Tối đa 10.000 dòng dữ liệu.')
    result = []
    bad_row = 'Số dòng Excel không hợp lệ hoặc vượt quá 10.001.'
    for row in sheet_rows:
        ref = row.get('r', '')
        row_number = _int(ref, bad_row) if ref else len(result) + 1
        if not len(result) < row_number <= MAX_ROWS:
            raise ValueError(bad_row)
        while len(result) < row_number - 1:
            result.append([])
        values = []
        for cell in _all(row, 'c'):
            col = 0
            for ch in cell.get('r', ''):
                if not 'A' <= ch <= 'Z':
                    break
                col = col * 26 + ord(ch) - ord('A') + 1
            col -= 1
            if not 0 <= col < MAX_COLUMNS:
                raise ValueError('File có cột không hợp lệ hoặc vượt quá 100 cột.')
            values.extend([''] * (col + 1 - len(values)))
            kind = cell.get('t', '')
            value = _text(cell, 't') if kind == 'inlineStr' else _text(cell, 'v')
            if kind == 's':
                index = _int(value.strip(), 'Ô Excel không hợp lệ.')
                if not 0 <= index < len(shared):
                    raise ValueError('Ô Excel không hợp lệ.')
                value = shared[index]
            values[col] = value
        result.append(values)
    return result


# ---- School export -------------------------------------------------------

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
DAYS = ('Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu')
SHIFTS = ('morning', 'afternoon')
XML_HEAD = '<?xml version="1.0" encoding="UTF-8"?>'
STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="16"/><color rgb="FF2E5D42"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FF355F48"/><name val="Calibri"/></font></fonts>
  <fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE4F0E2"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF2F7EF"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="2"><border/><border><left style="thin"><color rgb="FFDCE8DB"/></left><right style="thin"><color rgb="FFDCE8DB"/></right><top style="thin"><color rgb="FFDCE8DB"/></top><bottom style="thin"><color rgb="FFDCE8DB"/></bottom></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="7"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''
_ESCAPES = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'}


def _escape(value):
    out = []
    for ch in value:
        c = ord(ch)
        if c in (9, 10, 13) or 32 <= c <= 0xD7FF or 0xE000 <= c <= 0xFFFD or 0x10000 <= c <= 0x10FFFF:
            out.append(_ESCAPES.get(ch, ch))
    return ''.join(out)


def _grade(klass, name):
    raw = klass.get('grade')
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw in (6, 7, 8, 9):
        return str(int(raw))
    grade = text(klass, 'grade')
    if re.fullmatch('[6-9]', grade):
        return grade
    match = re.match(r'[ \t\n\x0b\f\r]*([6-9])', name)
    return match.group(1) if match else 'other'


def _natural(a, b):
    i = j = 0
    while i < len(a) and j < len(b):
        x, y = a[i], b[j]
        if x.isdecimal() and y.isdecimal():
            p, q = i, j
            while i < len(a) and a[i].isdecimal():
                i += 1
            while j < len(b) and b[j].isdecimal():
                j += 1
            left, right = a[p:i].lstrip('0') or '0', b[q:j].lstrip('0') or '0'
            if len(left) != len(right):
                return len(left) - len(right)
            if left != right:
                return -1 if left < right else 1
        else:
            if x.lower() != y.lower():
                return -1 if x.lower() < y.lower() else 1
            i += 1
            j += 1
    return (len(a) - i) - (len(b) - j)


def _col(i):
    name = ''
    while i > 0:
        name = chr(ord('A') + (i - 1) % 26) + name
        i = (i - 1) // 26
    return name


def _cell(row, col, value, style):
    return (f'<c r="{_col(col)}{row}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
            f'{_escape(value)}</t></is></c>')


def _row(row, height, cells):
    return f'<row r="{row}" ht="{height}" customHeight="1">{cells}</row>'


def _title(grade):
    return 'Chưa rõ khối' if grade == 'other' else f'Khối {grade}'


def _header(row, classes):
    cells = _cell(row, 1, 'THỨ', 4) + _cell(row, 2, 'TIẾT', 4)
    for i, (name, shift) in enumerate(classes):
        main = 'chính: sáng' if shift == 'morning' else 'chính: chiều'
        cells += _cell(row, i + 3, f'{name}\n({main})', 4)
    return _row(row, 34, cells)


def _sheet(grade, classes, cells, term):
    last_col = len(classes) + 2
    last = _col(last_col)
    x = [f'{XML_HEAD}<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0"><pane xSplit="2" ySplit="4" '
         'topLeftCell="C5" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>'
         '<sheetFormatPr defaultRowHeight="18"/><cols><col min="1" max="1" width="15" customWidth="1"/>'
         f'<col min="2" max="2" width="9" customWidth="1"/><col min="3" max="{last_col}" width="22" customWidth="1"/>'
         '</cols><sheetData>',
         _row(1, 30, _cell(1, 1, f'THỜI KHÓA BIỂU · {_title(grade)}', 1)),
         _row(2, 22, _cell(2, 1, term or 'Lịch toàn trường', 2)),
         _row(3, 22, _cell(3, 1, 'BUỔI SÁNG', 3)),
         _header(4, classes)]
    for shift, first in (('morning', 5), ('afternoon', 32)):
        if shift == 'afternoon':
            x += [_row(30, 22, _cell(30, 1, 'BUỔI CHIỀU', 3)), _header(31, classes)]
        for day in range(5):
            for period in range(1, 6):
                row = first + day * 5 + period - 1
                out = _cell(row, 1, DAYS[day] if period == 1 else '', 5) + _cell(row, 2, str(period), 5)
                for i, (name, _) in enumerate(classes):
                    lesson = cells.get((name, shift, day, period))
                    value = '' if lesson is None else lesson[0] + (f'\n{lesson[1]}' if lesson[1] else '')
                    out += _cell(row, i + 3, value, 6)
                x.append(_row(row, 36, out))
    x.append(f'</sheetData><mergeCells count="14"><mergeCell ref="A1:{last}1"/><mergeCell ref="A2:{last}2"/>'
             f'<mergeCell ref="A3:{last}3"/><mergeCell ref="A30:{last}30"/>')
    for start in (5, 32):
        for day in range(5):
            x.append(f'<mergeCell ref="A{start + day * 5}:A{start + day * 5 + 4}"/>')
    x.append('</mergeCells><pageMargins left="0.25" right="0.25" top="0.4" bottom="0.4" header="0.2" footer="0.2"/>'
             '<pageSetup orientation="landscape" fitToWidth="1"/></worksheet>')
    return ''.join(x)


def school_workbook(state):
    """Build a workbook with one timetable sheet per grade."""
    raw_classes, schedule, events = rows(state, 'classes'), rows(state, 'schedule'), rows(state, 'events')
    if not raw_classes or not schedule:
        raise ValueError('Hãy thêm lớp và xếp lịch trước khi xuất.')
    if len(raw_classes) > 1000:
        raise ValueError('Tối đa 1.000 lớp khi xuất Excel.')
    groups, shifts = {}, {}
    for klass in raw_classes:
        name, shift = text(klass, 'name'), text(klass, 'shift')
        if not name or shift not in SHIFTS or name in shifts:
            raise ValueError('Kiểm tra tên lớp, buổi học và tên lớp trùng trước khi xuất.')
        shifts[name] = shift
        groups.setdefault(_grade(klass, name), []).append((name, shift))
    by_name = functools.cmp_to_key(_natural)
    grades = sorted(groups, key=lambda g: (99 if g == 'other' else int(g), g))
    for grade in grades:
        groups[grade].sort(key=lambda c: by_name(c[0]))

    cells = {}
    for lesson in schedule:
        name, shift = text(lesson, 'className'), text(lesson, 'shift')
        subject, teacher = text(lesson, 'subject'), text(lesson, 'teacher')
        day, period = number(lesson, 'day', -1), number(lesson, 'period', 0)
        if name not in shifts or shift not in SHIFTS or not 0 <= day <= 4 or not 1 <= period <= 5 or not subject:
            raise ValueError('Lịch có tiết không hợp lệ. Hãy kiểm tra trước khi xuất.')
        if (name, shift, day, period) in cells:
            raise ValueError(f'Lớp {name} có hai nội dung cùng một tiết.')
        cells[name, shift, day, period] = (subject, teacher)
    for event in events:
        shift, name = text(event, 'shift'), text(event, 'name')
        day, period = number(event, 'day', -1), number(event, 'period', 0)
        if not name or shift not in SHIFTS or not 0 <= day <= 4 or not 1 <= period <= 5:
            raise ValueError('Hoạt động cố định không hợp lệ.')
        for klass, main in shifts.items():
            if main == shift:
                current = cells.setdefault((klass, shift, day, period), (name, ''))
                if current != (name, ''):
                    raise ValueError(f'Lớp {klass} có tiết trùng hoạt động cố định.')

    parts = {
        '[Content_Types].xml': XML_HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                  for i in range(1, len(grades) + 1)) + '</Types>',
        '_rels/.rels': XML_HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{REL_NS}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'{XML_HEAD}<workbook xmlns="{NS}" xmlns:r="{REL_NS}"><sheets>'
        + ''.join(f'<sheet name="{_escape(_title(g))}" sheetId="{i}" r:id="rId{i}"/>' for i, g in enumerate(grades, 1))
        + '</sheets></workbook>',
        'xl/_rels/workbook.xml.rels': XML_HEAD
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + ''.join(f'<Relationship Id="rId{i}" Type="{REL_NS}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                  for i in range(1, len(grades) + 1))
        + f'<Relationship Id="rId{len(grades) + 1}" Type="{REL_NS}/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml': STYLES,
    }
    term = text(state, 'term')
    for i, grade in enumerate(grades, 1):
        parts[f'xl/worksheets/sheet{i}.xml'] = _sheet(grade, groups[grade], cells, term)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data.encode('utf-8'))
    return buffer.getvalue()
