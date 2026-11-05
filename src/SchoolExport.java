import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.*;
import java.util.zip.*;

/** Creates a self-contained XLSX with one timetable sheet per grade. */
final class SchoolExport {
  private static final String NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main";
  private static final String[] DAYS={"Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu"};
  private record Slot(String name,String shift,int day,int period) {}
  private record Lesson(String subject,String teacher) {}
  private record Klass(String name,String grade,String mainShift) {}

  static byte[] create(Map<String,Object> state)throws IOException {
    List<Map<String,Object>> rawClasses=Main.Scheduler.list(state,"classes"), schedule=Main.Scheduler.list(state,"schedule"),events=Main.Scheduler.list(state,"events");
    if(rawClasses.isEmpty()||schedule.isEmpty())throw new IllegalArgumentException("Hãy thêm lớp và xếp lịch trước khi xuất.");
    if(rawClasses.size()>1000)throw new IllegalArgumentException("Tối đa 1.000 lớp khi xuất Excel.");
    Map<String,List<Klass>> groups=new TreeMap<>(Comparator.comparingInt(SchoolExport::gradeOrder).thenComparing(x->x));
    Map<String,Klass> classes=new LinkedHashMap<>();
    for(Map<String,Object> c:rawClasses){String name=Main.Scheduler.s(c,"name"),shift=Main.Scheduler.s(c,"shift");if(name.isEmpty()||!List.of("morning","afternoon").contains(shift)||classes.containsKey(name))throw new IllegalArgumentException("Kiểm tra tên lớp, buổi học và tên lớp trùng trước khi xuất.");String grade=grade(c,name);Klass klass=new Klass(name,grade,shift);classes.put(name,klass);groups.computeIfAbsent(grade,k->new ArrayList<>()).add(klass);}
    for(List<Klass> group:groups.values())group.sort(Comparator.comparing(Klass::name,SchoolExport::naturalCompare));
    Map<Slot,Lesson> cells=new HashMap<>();
    for(Map<String,Object> row:schedule){String name=Main.Scheduler.s(row,"className"),shift=Main.Scheduler.s(row,"shift"),subject=Main.Scheduler.s(row,"subject"),teacher=Main.Scheduler.s(row,"teacher");int day=Main.Scheduler.n(row,"day",-1),period=Main.Scheduler.n(row,"period",0);if(!classes.containsKey(name)||!List.of("morning","afternoon").contains(shift)||day<0||day>4||period<1||period>5||subject.isEmpty())throw new IllegalArgumentException("Lịch có tiết không hợp lệ. Hãy kiểm tra trước khi xuất.");Slot slot=new Slot(name,shift,day,period);if(cells.putIfAbsent(slot,new Lesson(subject,teacher))!=null)throw new IllegalArgumentException("Lớp "+name+" có hai nội dung cùng một tiết.");}
    for(Map<String,Object> event:events){String shift=Main.Scheduler.s(event,"shift"),name=Main.Scheduler.s(event,"name");int day=Main.Scheduler.n(event,"day",-1),period=Main.Scheduler.n(event,"period",0);if(name.isEmpty()||!List.of("morning","afternoon").contains(shift)||day<0||day>4||period<1||period>5)throw new IllegalArgumentException("Hoạt động cố định không hợp lệ.");for(Klass c:classes.values())if(c.mainShift().equals(shift)){Slot slot=new Slot(c.name(),shift,day,period);Lesson current=cells.get(slot);if(current==null)cells.put(slot,new Lesson(name,""));else if(!current.teacher().isEmpty()||!current.subject().equals(name))throw new IllegalArgumentException("Lớp "+c.name()+" có tiết trùng hoạt động cố định.");}}
    ByteArrayOutputStream buffer=new ByteArrayOutputStream();
    try(ZipOutputStream zip=new ZipOutputStream(buffer,StandardCharsets.UTF_8)){
      put(zip,"[Content_Types].xml",contentTypes(groups.size()));put(zip,"_rels/.rels",rootRels());put(zip,"xl/workbook.xml",workbook(groups));put(zip,"xl/_rels/workbook.xml.rels",workbookRels(groups.size()));put(zip,"xl/styles.xml",styles());
      int index=0;for(var entry:groups.entrySet())put(zip,"xl/worksheets/sheet"+(++index)+".xml",sheet(entry.getKey(),entry.getValue(),cells,Main.Scheduler.s(state,"term")));
    }
    return buffer.toByteArray();
  }

  private static String grade(Map<String,Object> c,String name){Object raw=c.get("grade");if(raw instanceof Number n&&n.doubleValue()==n.intValue()&&n.intValue()>=6&&n.intValue()<=9)return Integer.toString(n.intValue());String g=Main.Scheduler.s(c,"grade");if(g.matches("[6-9]"))return g;Matcher m=Pattern.compile("^\\s*([6-9])").matcher(name);return m.find()?m.group(1):"other";}
  private static int gradeOrder(String g){return g.equals("other")?99:Integer.parseInt(g);}
  private static int naturalCompare(String a,String b){int i=0,j=0;while(i<a.length()&&j<b.length()){char x=a.charAt(i),y=b.charAt(j);if(Character.isDigit(x)&&Character.isDigit(y)){int p=i,q=j;while(i<a.length()&&Character.isDigit(a.charAt(i)))i++;while(j<b.length()&&Character.isDigit(b.charAt(j)))j++;String left=a.substring(p,i).replaceFirst("^0+(?!$)",""),right=b.substring(q,j).replaceFirst("^0+(?!$)","");if(left.length()!=right.length())return Integer.compare(left.length(),right.length());int n=left.compareTo(right);if(n!=0)return n;}else{int n=Character.compare(Character.toLowerCase(x),Character.toLowerCase(y));if(n!=0)return n;i++;j++;}}return Integer.compare(a.length()-i,b.length()-j);}
  private static void put(ZipOutputStream zip,String name,String data)throws IOException{zip.putNextEntry(new ZipEntry(name));zip.write(data.getBytes(StandardCharsets.UTF_8));zip.closeEntry();}
  private static String escape(String s){StringBuilder b=new StringBuilder();s.codePoints().forEach(c->{if(c==9||c==10||c==13||c>=32&&c<=0xD7FF||c>=0xE000&&c<=0xFFFD||c>=0x10000&&c<=0x10FFFF){switch(c){case '&'->b.append("&amp;");case '<'->b.append("&lt;");case '>'->b.append("&gt;");case '"'->b.append("&quot;");case '\''->b.append("&apos;");default->b.appendCodePoint(c);}}});return b.toString();}
  private static String col(int i){StringBuilder b=new StringBuilder();for(int n=i;n>0;n=(n-1)/26)b.append((char)('A'+(n-1)%26));return b.reverse().toString();}
  private static String cell(int row,int col,String value,int style){return "<c r=\""+col(col)+row+"\" s=\""+style+"\" t=\"inlineStr\"><is><t xml:space=\"preserve\">"+escape(value)+"</t></is></c>";}
  private static String title(String grade){return grade.equals("other")?"Chưa rõ khối":"Khối "+grade;}
  private static String sheet(String grade,List<Klass> classes,Map<Slot,Lesson> cells,String term){
    int lastCol=classes.size()+2;String last=col(lastCol);StringBuilder x=new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?><worksheet xmlns=\"").append(NS).append("\"><sheetViews><sheetView workbookViewId=\"0\"><pane xSplit=\"2\" ySplit=\"4\" topLeftCell=\"C5\" activePane=\"bottomRight\" state=\"frozen\"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight=\"18\"/><cols><col min=\"1\" max=\"1\" width=\"15\" customWidth=\"1\"/><col min=\"2\" max=\"2\" width=\"9\" customWidth=\"1\"/><col min=\"3\" max=\"").append(lastCol).append("\" width=\"22\" customWidth=\"1\"/></cols><sheetData>");
    row(x,1,30,cell(1,1,"THỜI KHÓA BIỂU · "+title(grade),1));row(x,2,22,cell(2,1,term.isEmpty()?"Lịch toàn trường":term,2));row(x,3,22,cell(3,1,"BUỔI SÁNG",3));header(x,4,classes);
    for(int day=0;day<5;day++)for(int period=1;period<=5;period++)lessonRow(x,5+day*5+period-1,classes,cells,"morning",day,period);
    row(x,30,22,cell(30,1,"BUỔI CHIỀU",3));header(x,31,classes);
    for(int day=0;day<5;day++)for(int period=1;period<=5;period++)lessonRow(x,32+day*5+period-1,classes,cells,"afternoon",day,period);
    x.append("</sheetData><mergeCells count=\"14\"><mergeCell ref=\"A1:").append(last).append("1\"/><mergeCell ref=\"A2:").append(last).append("2\"/><mergeCell ref=\"A3:").append(last).append("3\"/><mergeCell ref=\"A30:").append(last).append("30\"/>");
    for(int start:new int[]{5,32})for(int day=0;day<5;day++)x.append("<mergeCell ref=\"A").append(start+day*5).append(":A").append(start+day*5+4).append("\"/>");
    x.append("</mergeCells><pageMargins left=\"0.25\" right=\"0.25\" top=\"0.4\" bottom=\"0.4\" header=\"0.2\" footer=\"0.2\"/><pageSetup orientation=\"landscape\" fitToWidth=\"1\"/></worksheet>");
    return x.toString();
  }
  private static void row(StringBuilder x,int row,int height,String cells){x.append("<row r=\"").append(row).append("\" ht=\"").append(height).append("\" customHeight=\"1\">").append(cells).append("</row>");}
  private static void header(StringBuilder x,int row,List<Klass> classes){StringBuilder cells=new StringBuilder(cell(row,1,"THỨ",4)).append(cell(row,2,"TIẾT",4));for(int i=0;i<classes.size();i++){Klass c=classes.get(i);cells.append(cell(row,i+3,c.name()+"\n("+(c.mainShift().equals("morning")?"chính: sáng":"chính: chiều")+")",4));}row(x,row,34,cells.toString());}
  private static void lessonRow(StringBuilder x,int row,List<Klass> classes,Map<Slot,Lesson> cells,String shift,int day,int period){StringBuilder out=new StringBuilder(cell(row,1,period==1?DAYS[day]:"",5)).append(cell(row,2,String.valueOf(period),5));for(int i=0;i<classes.size();i++){Lesson lesson=cells.get(new Slot(classes.get(i).name(),shift,day,period));String text=lesson==null?"":lesson.subject()+(lesson.teacher().isEmpty()?"":"\n"+lesson.teacher());out.append(cell(row,i+3,text,6));}row(x,row,36,out.toString());}
  private static String rootRels(){return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>";}
  private static String contentTypes(int count){StringBuilder x=new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>");for(int i=1;i<=count;i++)x.append("<Override PartName=\"/xl/worksheets/sheet").append(i).append(".xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>");return x.append("</Types>").toString();}
  private static String workbook(Map<String,List<Klass>> groups){StringBuilder x=new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?><workbook xmlns=\"").append(NS).append("\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets>");int i=0;for(String grade:groups.keySet()){i++;x.append("<sheet name=\"").append(escape(title(grade))).append("\" sheetId=\"").append(i).append("\" r:id=\"rId").append(i).append("\"/>");}return x.append("</sheets></workbook>").toString();}
  private static String workbookRels(int count){StringBuilder x=new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">");for(int i=1;i<=count;i++)x.append("<Relationship Id=\"rId").append(i).append("\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet").append(i).append(".xml\"/>");return x.append("<Relationship Id=\"rId").append(count+1).append("\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>").toString();}
  private static String styles(){return """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="16"/><color rgb="FF2E5D42"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FF355F48"/><name val="Calibri"/></font></fonts>
      <fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE4F0E2"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF2F7EF"/><bgColor indexed="64"/></patternFill></fill></fills>
      <borders count="2"><border/><border><left style="thin"><color rgb="FFDCE8DB"/></left><right style="thin"><color rgb="FFDCE8DB"/></right><top style="thin"><color rgb="FFDCE8DB"/></top><bottom style="thin"><color rgb="FFDCE8DB"/></bottom></border></borders>
      <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
      <cellXfs count="7"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs>
      <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
    </styleSheet>
    """.strip();}
}
