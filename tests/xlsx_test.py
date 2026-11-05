import io
import json
import os
import urllib.request
import zipfile

workbook = io.BytesIO()
with zipfile.ZipFile(workbook, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Mẫu" sheetId="1" r:id="rId1"/></sheets></workbook>')
    archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
    archive.writestr('xl/sharedStrings.xml', '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Tên lớp</t></si><si><t>9/1</t></si></sst>')
    archive.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>Buổi</t></is></c></row><row r="2"><c r="A2" t="s"><v>1</v></c><c r="C2" t="inlineStr"><is><t>Sáng</t></is></c></row></sheetData></worksheet>')
cookie = os.environ.get('AUTH_TEST_COOKIE')
user = os.environ.get('AUTH_TEST_USER')
if not cookie or not user:
    raise SystemExit('Provide a test-session cookie and user via AUTH_TEST_COOKIE and AUTH_TEST_USER.')
req = urllib.request.Request('http://localhost:3000/api/import-xlsx', data=workbook.getvalue(), method='POST', headers={'Content-Type':'application/octet-stream', 'Cookie':cookie, 'X-LT-User':user})
with urllib.request.urlopen(req) as response:
    rows = json.load(response)
assert rows == [['Tên lớp', '', 'Buổi'], ['9/1', '', 'Sáng']], rows
print('XLSX shared strings, inline strings, Unicode and missing columns passed')
