import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;
public class SpreadsheetRowsTest {
  static void add(ZipOutputStream zip,String name,String xml)throws Exception{zip.putNextEntry(new ZipEntry(name));zip.write(xml.getBytes(StandardCharsets.UTF_8));zip.closeEntry();}
  public static void main(String[] args)throws Exception{
    ByteArrayOutputStream out=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(out)){
      add(zip,"xl/workbook.xml","<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'><sheets><sheet name='Sheet1' sheetId='1' r:id='rId1'/></sheets></workbook>");
      add(zip,"xl/_rels/workbook.xml.rels","<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Target='worksheets/sheet1.xml'/></Relationships>");
      add(zip,"xl/worksheets/sheet1.xml","<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData><row r='1'><c r='A1' t='inlineStr'><is><t>Giáo viên</t></is></c></row><row r='2'><c r='A2' t='inlineStr'><is><t>T.Sương</t></is></c></row><row r='4'><c r='B4' t='inlineStr'><is><t>9/2</t></is></c></row></sheetData></worksheet>");
    }
    List<?> rows=(List<?>)Main.Xlsx.read(out.toByteArray());if(rows.size()!=4||!((List<?>)rows.get(2)).isEmpty()||!"9/2".equals(((List<?>)rows.get(3)).get(1)))throw new AssertionError("Missing physical rows must remain empty");
    System.out.println("Excel row gaps are preserved for safe teacher group handling.");
  }
}
