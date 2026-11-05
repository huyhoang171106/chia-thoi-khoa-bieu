import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
with ZipFile(Path('build/test-school-export.xlsx')) as book:
    for name in book.namelist():
        if name.endswith(('.xml', '.rels')):
            ET.fromstring(book.read(name))
    workbook = ET.fromstring(book.read('xl/workbook.xml'))
    names = [sheet.attrib['name'] for sheet in workbook.findall('x:sheets/x:sheet', NS)]
    assert names == ['Khối 6', 'Khối 7', 'Chưa rõ khối'], names
    def cells(index):
        sheet = ET.fromstring(book.read(f'xl/worksheets/sheet{index}.xml'))
        return {c.attrib['r']: ''.join(c.itertext()) for c in sheet.findall('.//x:sheetData/x:row/x:c', NS)}
    grade6 = cells(1)
    assert grade6['C4'].startswith('6/2') and grade6['D4'].startswith('6/10')
    assert grade6['C6'] == 'Toán & Lý\nCô <Lan>', grade6['C6']
    assert grade6['C45'] == 'Thể dục\nThầy An', grade6['C45']
    assert grade6['C5'] == 'Chào cờ' and grade6['D5'] == 'Chào cờ'
    grade7 = cells(2)
    assert grade7['C56'] == '=1+1\nGiáo viên'
    sheet7 = ET.fromstring(book.read('xl/worksheets/sheet2.xml'))
    assert not sheet7.findall('.//x:f', NS), 'User text must never become a spreadsheet formula'
    assert cells(3)['C4'].startswith('Khác')
print('Grade sheets, natural class order, both shifts, fixed activities and safe text passed.')
