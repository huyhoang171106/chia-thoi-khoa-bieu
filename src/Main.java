import com.sun.net.httpserver.*;
import java.net.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.io.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.zip.*;
import javax.xml.parsers.*;
import org.w3c.dom.*;

public class Main {
  static final Path ROOT = Paths.get("public").toAbsolutePath().normalize();
  public static void main(String[] args) throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 3000), 0);
    server.createContext("/api/auth", Auth::handle);
    server.createContext("/api/import-xlsx", e -> {
      try { if(!Auth.authorize(e))return;if(!e.getRequestMethod().equals("POST")){reply(e,405,"application/json","{}");return;}byte[] data=e.getRequestBody().readNBytes(5_000_001);if(data.length>5_000_000)throw new IllegalArgumentException("File vượt quá 5 MB.");reply(e,200,"application/json",Json.stringify(Xlsx.read(data))); }
      catch(Exception ex){reply(e,400,"application/json",Json.stringify(Map.of("error",ex.getMessage()==null?"Không đọc được file Excel.":ex.getMessage())));}
    });
    server.createContext("/api/export-school-xlsx", e -> {
      try {
        if(!Auth.authorize(e))return;
        if(!e.getRequestMethod().equals("POST")){reply(e,405,"application/json","{}");return;}
        byte[] body=e.getRequestBody().readNBytes(2_000_001);if(body.length>2_000_000)throw new IllegalArgumentException("Dữ liệu quá lớn để xuất Excel.");
        Object value=new Json(new String(body,StandardCharsets.UTF_8)).parse();if(!(value instanceof Map<?,?>))throw new IllegalArgumentException("Dữ liệu xuất không hợp lệ.");
        byte[] output=SchoolExport.create((Map<String,Object>)value);
        e.getResponseHeaders().set("Content-Type","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        e.getResponseHeaders().set("Content-Disposition","attachment; filename=\"thoi-khoa-bieu-toan-truong.xlsx\"");
        e.getResponseHeaders().set("Cache-Control","no-store");e.sendResponseHeaders(200,output.length);try(OutputStream out=e.getResponseBody()){out.write(output);}
      }catch(IllegalArgumentException ex){reply(e,400,"application/json",Json.stringify(Map.of("error",Objects.toString(ex.getMessage(),"Không thể xuất Excel."))));}
      catch(Exception ex){reply(e,500,"application/json",Json.stringify(Map.of("error","Không thể tạo file Excel. Hãy thử lại.")));}
    });
    server.createContext("/api/state", e -> {
      try {
        if(!Auth.authorize(e))return;
        String token=Auth.token(e);
        if(e.getRequestMethod().equals("GET")) { String data=Auth.loadState(token); if(data==null){reply(e,401,"application/json","{\"error\":\"Phiên đăng nhập đã hết hiệu lực.\"}");return;}reply(e,200,"application/json",data.equals("null")?"null":cleanState(data)); }
        else if(e.getRequestMethod().equals("PUT")) { byte[] body=e.getRequestBody().readNBytes(2_000_001);if(body.length>2_000_000)throw new IllegalArgumentException("Dữ liệu quá lớn.");String data=cleanState(new String(body,StandardCharsets.UTF_8));validateTeacherNames(data);if(!Auth.saveState(token,data)){reply(e,401,"application/json","{\"error\":\"Phiên đăng nhập đã hết hiệu lực.\"}");return;}reply(e,200,"application/json","{\"ok\":true}"); }
        else reply(e,405,"application/json","{}");
      } catch(IllegalArgumentException ex) { reply(e,400,"application/json",Json.stringify(Map.of("error",Objects.toString(ex.getMessage(),"Dữ liệu không hợp lệ.")))); } catch(Exception ex) { reply(e,503,"application/json",Json.stringify(Map.of("error",ex.getMessage()==null?"Không kết nối được SQL Server.":ex.getMessage()))); }
    });
    server.createContext("/api/generate", e -> {
      try {
        if(!Auth.authorize(e))return;
        if (!e.getRequestMethod().equals("POST")) { reply(e,405,"application/json","{}" ); return; }
        Object value = new Json(new String(e.getRequestBody().readAllBytes(), StandardCharsets.UTF_8)).parse();
        reply(e,200,"application/json",Json.stringify(new Scheduler((Map<String,Object>)value).run()));
      } catch (Exception ex) { reply(e,400,"application/json",Json.stringify(Map.of("error", ex.getMessage() == null ? "Dữ liệu không hợp lệ" : ex.getMessage()))); }
    });
    server.createContext("/api/generate-stream", e -> {
      try{if(!Auth.authorize(e))return;}catch(Exception ex){reply(e,503,"application/json",Json.stringify(Map.of("error","Không xác thực được phiên đăng nhập.")));return;}
      if(!e.getRequestMethod().equals("POST")){reply(e,405,"application/json","{}");return;}
      Object value;
      try { byte[] body=e.getRequestBody().readNBytes(2_000_001);if(body.length>2_000_000)throw new IllegalArgumentException("Dữ liệu quá lớn.");value=new Json(new String(body,StandardCharsets.UTF_8)).parse();if(!(value instanceof Map))throw new IllegalArgumentException("Dữ liệu không hợp lệ."); }
      catch(Exception ex){reply(e,400,"application/json",Json.stringify(Map.of("error",Objects.toString(ex.getMessage(),"Dữ liệu không hợp lệ."))));return;}
      e.getResponseHeaders().set("Content-Type","application/x-ndjson; charset=utf-8");
      e.getResponseHeaders().set("Cache-Control","no-store");
      e.sendResponseHeaders(200,0);
      try(OutputStream out=e.getResponseBody()){
        java.util.function.Consumer<Map<String,Object>> send=event->{try{out.write((Json.stringify(event)+"\n").getBytes(StandardCharsets.UTF_8));out.flush();}catch(IOException ex){throw new UncheckedIOException(ex);}};
        try {send.accept(Map.of("type","progress","phase","search","elapsed",0));Map<String,Object> result=CpScheduler.run((Map<String,Object>)value,send);send.accept(Map.of("type","result","result",result));}
        catch(UncheckedIOException ex){throw ex;}
        catch(Exception ex){send.accept(Map.of("type","error","error",Objects.toString(ex.getMessage(),"Dữ liệu không hợp lệ.")));}
      }catch(UncheckedIOException ignored){}
    });
    server.createContext("/", e -> {
      try {
        String name = e.getRequestURI().getPath(); if (name.equals("/")) name="/index.html";
        Path file=ROOT.resolve(name.substring(1)).normalize();
        if(!file.startsWith(ROOT) || !Files.isRegularFile(file)) { reply(e,404,"text/plain","Not found"); return; }
        String type=name.endsWith(".css")?"text/css":name.endsWith(".js")?"text/javascript":"text/html";
        reply(e,200,type,Files.readString(file));
      } catch(Exception ex) { reply(e,500,"text/plain","Server error"); }
    });
    server.setExecutor(java.util.concurrent.Executors.newCachedThreadPool()); server.start();
    System.out.println("Lịch Trường đang chạy tại http://localhost:3000");
  }
  static void reply(HttpExchange e,int code,String type,String body)throws IOException { byte[] b=body.getBytes(StandardCharsets.UTF_8); e.getResponseHeaders().set("Content-Type",type+"; charset=utf-8"); e.sendResponseHeaders(code,b.length); try(OutputStream out=e.getResponseBody()){out.write(b);} }
  static String cleanState(String data){Object value=new Json(data).parse();if(!(value instanceof Map))throw new IllegalArgumentException("Dữ liệu không hợp lệ.");Map<?,?> state=(Map<?,?>)value;state.remove("closed");return Json.stringify(state);}
  static String teacherKey(String name){return java.text.Normalizer.normalize(name.trim().replaceAll("(?U)\\s+"," "),java.text.Normalizer.Form.NFC).toLowerCase(Locale.forLanguageTag("vi"));}
  static void validateTeacherNames(String data){Map<?,?> state=(Map<?,?>)new Json(data).parse();Object raw=state.get("teachers");if(!(raw instanceof List<?> teachers))return;Set<String> seen=new HashSet<>();for(Object item:teachers){if(!(item instanceof Map<?,?> teacher))throw new IllegalArgumentException("Dữ liệu giáo viên không hợp lệ.");String name=Objects.toString(teacher.get("name"),"");String key=teacherKey(name);if(!key.isEmpty()&&!seen.add(key))throw new IllegalArgumentException("Tên giáo viên bị trùng: "+name.trim()+". Hãy giữ một giáo viên duy nhất.");}}
  static class Xlsx {
    static Document xml(byte[] bytes)throws Exception{DocumentBuilderFactory f=DocumentBuilderFactory.newInstance();f.setNamespaceAware(true);f.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);f.setFeature("http://xml.org/sax/features/external-general-entities",false);f.setFeature("http://xml.org/sax/features/external-parameter-entities",false);f.setXIncludeAware(false);f.setExpandEntityReferences(false);return f.newDocumentBuilder().parse(new ByteArrayInputStream(bytes));}
    static String text(Element parent,String local){NodeList nodes=parent.getElementsByTagNameNS("*",local);StringBuilder b=new StringBuilder();for(int i=0;i<nodes.getLength();i++)b.append(nodes.item(i).getTextContent());return b.toString();}
    static Object read(byte[] bytes)throws Exception{
      Map<String,byte[]> files=new HashMap<>();int total=0;try(ZipInputStream zip=new ZipInputStream(new ByteArrayInputStream(bytes))){ZipEntry entry;while((entry=zip.getNextEntry())!=null){if(entry.isDirectory())continue;ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;while((n=zip.read(buffer))!=-1){total+=n;if(total>20_000_000)throw new IllegalArgumentException("File Excel sau giải nén quá lớn.");out.write(buffer,0,n);}files.put(entry.getName(),out.toByteArray());if(files.size()>2000)throw new IllegalArgumentException("File Excel có quá nhiều thành phần.");}}
      if(!files.containsKey("xl/workbook.xml")||!files.containsKey("xl/_rels/workbook.xml.rels"))throw new IllegalArgumentException("File không phải Excel .xlsx hợp lệ.");
      Document book=xml(files.get("xl/workbook.xml"));NodeList sheets=book.getElementsByTagNameNS("*","sheet");if(sheets.getLength()==0)throw new IllegalArgumentException("File không có trang tính.");String rid=((Element)sheets.item(0)).getAttributeNS("http://schemas.openxmlformats.org/officeDocument/2006/relationships","id");Document rel=xml(files.get("xl/_rels/workbook.xml.rels"));NodeList relations=rel.getElementsByTagNameNS("*","Relationship");String target=null;for(int i=0;i<relations.getLength();i++){Element r=(Element)relations.item(i);if(r.getAttribute("Id").equals(rid)&&!r.getAttribute("TargetMode").equalsIgnoreCase("External"))target=r.getAttribute("Target");}if(target==null)throw new IllegalArgumentException("Không tìm thấy trang tính đầu tiên.");String path=target.startsWith("/")?target.substring(1):"xl/"+target;path=Paths.get(path).normalize().toString().replace('\\','/');if(!path.startsWith("xl/")||!files.containsKey(path))throw new IllegalArgumentException("Không đọc được trang tính đầu tiên.");
      List<String> shared=new ArrayList<>();if(files.containsKey("xl/sharedStrings.xml")){NodeList si=xml(files.get("xl/sharedStrings.xml")).getElementsByTagNameNS("*","si");for(int i=0;i<si.getLength();i++)shared.add(text((Element)si.item(i),"t"));}
      NodeList rows=xml(files.get(path)).getElementsByTagNameNS("*","row");if(rows.getLength()>10001)throw new IllegalArgumentException("Tối đa 10.000 dòng dữ liệu.");List<List<String>> result=new ArrayList<>();for(int i=0;i<rows.getLength();i++){Element row=(Element)rows.item(i);String rowRef=row.getAttribute("r");int rowNum=rowRef.isEmpty()?result.size()+1:Integer.parseInt(rowRef);if(rowNum<1||rowNum>10001||rowNum<=result.size())throw new IllegalArgumentException("Số dòng Excel không hợp lệ hoặc vượt quá 10.001.");while(result.size()<rowNum-1)result.add(new ArrayList<>());NodeList cells=row.getElementsByTagNameNS("*","c");List<String> values=new ArrayList<>();for(int j=0;j<cells.getLength();j++){Element cell=(Element)cells.item(j);String ref=cell.getAttribute("r");int col=0;for(char ch:ref.toCharArray()){if(ch<'A'||ch>'Z')break;col=col*26+(ch-'A'+1);}col--;if(col<0||col>=100)throw new IllegalArgumentException("File có cột không hợp lệ hoặc vượt quá 100 cột.");while(values.size()<=col)values.add("");String type=cell.getAttribute("t"),v=type.equals("inlineStr")?text(cell,"t"):text(cell,"v");if(type.equals("s")){int idx=Integer.parseInt(v);if(idx<0||idx>=shared.size())throw new IllegalArgumentException("Ô Excel không hợp lệ.");v=shared.get(idx);}values.set(col,v);}result.add(values);}return result;
    }
  }
  static class SqlStore {
    static Map<String,String> config() throws IOException {
      Path path=Paths.get(System.getenv().getOrDefault("LT_ENV_FILE",".env"));if(!Files.isRegularFile(path))throw new IOException("Chưa có file .env ở thư mục gốc.");Map<String,String> env=new HashMap<>();
      for(String line:Files.readAllLines(path,StandardCharsets.UTF_8)){line=line.trim();if(line.isEmpty()||line.startsWith("#"))continue;int eq=line.indexOf('=');if(eq<1)continue;String value=line.substring(eq+1).trim();if(value.length()>=2&&((value.startsWith("\"")&&value.endsWith("\""))||(value.startsWith("'")&&value.endsWith("'"))))value=value.substring(1,value.length()-1);env.put(line.substring(0,eq).trim(),value);}
      for(String key:List.of("DB_HOST","DB_PORT","DB_NAME","DB_USER","DB_PASSWORD"))if(env.getOrDefault(key,"").isEmpty())throw new IOException("Thiếu "+key+" trong file .env.");
      if(!env.get("DB_PORT").matches("[0-9]{1,5}")||!env.get("DB_HOST").matches("[A-Za-z0-9._-]+")||!env.get("DB_NAME").matches("[A-Za-z0-9_-]+"))throw new IOException("Kiểm tra DB_HOST, DB_PORT và DB_NAME trong .env.");return env;
    }
    static String query(String sql) throws Exception {
      Map<String,String> cfg=config();ProcessBuilder pb=new ProcessBuilder("powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File","scripts/sql-query.ps1");for(String key:List.of("DB_HOST","DB_PORT","DB_NAME","DB_USER","DB_PASSWORD"))pb.environment().put("LT_"+key,cfg.get(key));pb.redirectErrorStream(true);Process p;
      try {p=pb.start();}catch(IOException ex){throw new IOException("Không tìm thấy Windows PowerShell để kết nối SQL Server.");}
      try(OutputStream out=p.getOutputStream()){out.write(sql.getBytes(StandardCharsets.UTF_8));}
      java.util.concurrent.CompletableFuture<byte[]> read=java.util.concurrent.CompletableFuture.supplyAsync(()->{try{return p.getInputStream().readAllBytes();}catch(IOException ex){return new byte[0];}});
      if(!p.waitFor(15,TimeUnit.SECONDS)){p.destroyForcibly();throw new IOException("SQL Server không phản hồi. Kiểm tra máy chủ và cổng trong .env.");}
      String result=new String(read.get(3,TimeUnit.SECONDS),StandardCharsets.UTF_8).trim();if(p.exitValue()!=0)throw new IOException(switch(result){case "LOGIN"->"SQL Server từ chối đăng nhập. Kiểm tra DB_USER và DB_PASSWORD.";case "DATABASE"->"Không mở được database. Kiểm tra DB_NAME và quyền truy cập.";case "PERMISSION"->"Tài khoản chưa có quyền đọc, ghi hoặc tạo bảng trong database.";default->"Không kết nối hoặc truy vấn được SQL Server. Kiểm tra cấu hình và quyền truy cập.";});return result;
    }
    static final String INIT="SET NOCOUNT ON; IF OBJECT_ID(N'dbo.LichTruongState', N'U') IS NULL CREATE TABLE dbo.LichTruongState (id int NOT NULL PRIMARY KEY, data nvarchar(max) NOT NULL); ";
    static synchronized String load() throws Exception {
      String out=query(INIT+"SELECT CAST(N'' AS XML).value('xs:base64Binary(sql:column(\"data\"))', 'varchar(max)') FROM (SELECT CONVERT(varbinary(max), data) AS data FROM dbo.LichTruongState WHERE id=1) AS s;");
      if(out.isBlank())return null;try{return new String(Base64.getDecoder().decode(out.replaceAll("\\s+","")),StandardCharsets.UTF_16LE);}catch(IllegalArgumentException ex){throw new IOException("Không đọc được dữ liệu từ SQL Server.");}
    }
    static synchronized void save(String data) throws Exception {
      String hex=HexFormat.of().formatHex(data.getBytes(StandardCharsets.UTF_16LE));query(INIT+"DECLARE @data nvarchar(max)=CONVERT(nvarchar(max),0x"+hex+"); UPDATE dbo.LichTruongState SET data=@data WHERE id=1; IF @@ROWCOUNT=0 INSERT INTO dbo.LichTruongState(id,data) VALUES(1,@data);");
    }
  }
  static class Scheduler {
    Map<String,Object> input; List<Map<String,Object>> classes, teachers, assignments, events; Random rand=new Random();
    Map<String,Integer> max=new HashMap<>(); Map<String,String> shifts=new HashMap<>(); Map<String,Integer> sessions=new HashMap<>();
    int[][][] grid; boolean[][][] busy,lockedGrid; int[][] teacherLoad; List<Map<String,Object>> best; int bestScore=Integer.MAX_VALUE; long nodes; boolean exhausted; int[][] extraPairs;
    final java.util.function.IntConsumer progress;final boolean untilFound;final int attemptLimit;
    Scheduler(Map<String,Object> in){this(in,ignored->{});}
    Scheduler(Map<String,Object> in,java.util.function.IntConsumer progress){this(in,progress,false);}
    Scheduler(Map<String,Object> in,java.util.function.IntConsumer progress,boolean untilFound){this(in,progress,untilFound,70);}
    Scheduler(Map<String,Object> in,java.util.function.IntConsumer progress,boolean untilFound,int attemptLimit){input=in;this.progress=progress;this.untilFound=untilFound;this.attemptLimit=attemptLimit; classes=list(in,"classes");teachers=list(in,"teachers");assignments=list(in,"assignments");events=list(in,"events");}
    static List<Map<String,Object>> list(Map<String,Object> m,String k){return (List<Map<String,Object>>)m.getOrDefault(k,List.of());}
    static String s(Map<String,Object> m,String k){return Objects.toString(m.get(k),"").trim();} static int n(Map<String,Object> m,String k,int d){Object v=m.get(k);try{return v instanceof Number?((Number)v).intValue():Integer.parseInt(v.toString());}catch(Exception e){return d;}}
    static String subjectKey(String subject){return java.text.Normalizer.normalize(subject.toLowerCase(Locale.ROOT),java.text.Normalizer.Form.NFD).replaceAll("\\p{M}+","").replace('đ','d').replaceAll("[^a-z0-9]","");}
    static int extraKind(String subject){String key=subjectKey(subject);return key.equals("hoatdongtrainghiem")?1:key.equals("theduc")?2:0;}
    static boolean literature(String subject){return Set.of("van","nguvan").contains(subjectKey(subject));}
    static boolean flexibleDays(String subject){return Set.of("toan","anh","tienganh").contains(subjectKey(subject));}
    static boolean sameLimitedSubject(String a,String b){String x=subjectKey(a),y=subjectKey(b);return x.equals("toan")&&y.equals("toan")||Set.of("anh","tienganh").contains(x)&&Set.of("anh","tienganh").contains(y);}
    static int minSessions(Map<String,Object> teacher){String rule=s(teacher,"sessionRule");if(rule.isEmpty()||rule.equals("standard"))return 4;if(rule.matches("[1-6]"))return Integer.parseInt(rule);throw new IllegalArgumentException("Số buổi dạy riêng của giáo viên không hợp lệ.");}
    static int maxSessions(Map<String,Object> teacher){String rule=s(teacher,"sessionRule");return rule.isEmpty()||rule.equals("standard")?5:minSessions(teacher);}
    static boolean teacherUnavailable(Map<String,Object> teacher,int session,int period){String rule=s(teacher,"offRule");if(rule.isEmpty()||rule.equals("standard"))return false;if(rule.equals("first"))return period==0;if(rule.matches("day:[0-4]"))return session%6==Integer.parseInt(rule.substring(4));if(rule.matches("session:[0-4]:(morning|afternoon)")){String[] parts=rule.split(":");return session%6==Integer.parseInt(parts[1])&&(session<6)==parts[2].equals("morning");}throw new IllegalArgumentException("Thời gian nghỉ của giáo viên không hợp lệ.");}
    static String opposite(String shift){return shift.equals("morning")?"afternoon":"morning";}
    String assignmentShift(Map<String,Object> a){String main=shifts.get(s(a,"className"));return extraKind(s(a,"subject"))>0?opposite(main):main;}
    Map<String,Object> run(){
      if(classes.isEmpty()||teachers.isEmpty()||assignments.isEmpty())throw new IllegalArgumentException("Hãy nhập lớp, giáo viên và phân công trước khi xếp lịch.");
      Set<String> teacherNames=new HashSet<>();for(int i=0;i<teachers.size();i++){String name=s(teachers.get(i),"name");if(name.isEmpty()||!teacherNames.add(teacherKey(name)))throw new IllegalArgumentException("Tên giáo viên không được trống hoặc trùng.");minSessions(teachers.get(i));teacherUnavailable(teachers.get(i),0,0);max.put(name,i);}
      for(Map<String,Object> c:classes){String name=s(c,"name"),shift=s(c,"shift");if(name.isEmpty()||shifts.containsKey(name)||(!shift.equals("morning")&&!shift.equals("afternoon")))throw new IllegalArgumentException("Kiểm tra tên lớp và buổi học; tên lớp không được trùng.");shifts.put(name,shift);}
      for(Map<String,Object> a:assignments){if(!shifts.containsKey(s(a,"className"))||!max.containsKey(s(a,"teacher"))||s(a,"subject").isEmpty()||n(a,"periods",0)<1||n(a,"periods",0)>30)throw new IllegalArgumentException("Kiểm tra phân công: lớp, giáo viên, môn và số tiết từ 1 đến 30.");}
      for(Map<String,Object> teacher:teachers){String name=s(teacher,"name");int total=0,min=minSessions(teacher),limit=maxSessions(teacher);for(Map<String,Object>a:assignments)if(s(a,"teacher").equals(name))total+=n(a,"periods",0);if(total>0&&total<2*min)throw new IllegalArgumentException("Giáo viên "+name+" chỉ có "+total+" tiết phân công, không đủ để dạy ít nhất 2 tiết mỗi buổi trong "+min+" buổi/tuần.");if(total>limit*5)throw new IllegalArgumentException("Giáo viên "+name+" có "+total+" tiết, vượt sức chứa tối đa của "+limit+" buổi/tuần.");}
      extraPairs=new int[classes.size()][2];for(int[] pair:extraPairs)Arrays.fill(pair,-1);boolean anyExtra=false;
      for(int i=0;i<assignments.size();i++){Map<String,Object>a=assignments.get(i);int kind=extraKind(s(a,"subject"));if(kind==0)continue;anyExtra=true;int c=classIndex(s(a,"className"));if(extraPairs[c][kind-1]>=0||n(a,"periods",0)!=2)throw new IllegalArgumentException("Mỗi lớp cần một phân công 2 tiết cho mỗi môn Hoạt động trải nghiệm và Thể dục.");extraPairs[c][kind-1]=i;}
      if(anyExtra)for(int c=0;c<classes.size();c++)if(extraPairs[c][0]<0||extraPairs[c][1]<0)throw new IllegalArgumentException("Lớp "+s(classes.get(c),"name")+" cần phân công đủ 2 tiết Hoạt động trải nghiệm và 2 tiết Thể dục.");
      for(Map<String,Object> ev:events)if(n(ev,"day",-1)<0||n(ev,"day",-1)>4||n(ev,"period",0)<1||n(ev,"period",0)>5||s(ev,"name").isEmpty()||!List.of("morning","afternoon").contains(s(ev,"shift")))throw new IllegalArgumentException("Hoạt động cố định chỉ được xếp từ thứ Hai đến thứ Sáu, tiết 1–5.");
      for(int attempt=0;untilFound||attempt<attemptLimit;attempt++){
        grid=new int[classes.size()][12][5]; lockedGrid=new boolean[classes.size()][12][5];busy=new boolean[teachers.size()][12][5];teacherLoad=new int[teachers.size()][12];
        for(int[][] g:grid)for(int[] d:g)Arrays.fill(d,-1);
        boolean invalid=false;
        for(int ei=0;ei<events.size();ei++){Map<String,Object> ev=events.get(ei);int day=n(ev,"day",-1)+(s(ev,"shift").equals("morning")?0:6),p=n(ev,"period",0)-1; for(int c=0;c<classes.size();c++)if(s(classes.get(c),"shift").equals(s(ev,"shift"))){if(grid[c][day][p]!=-1)invalid=true;else grid[c][day][p]=-10-ei;}}
        if(invalid)throw new IllegalArgumentException("Hai hoạt động cố định đang trùng cùng một tiết.");
        List<Integer> tasks=new ArrayList<>();int[] classCount=new int[classes.size()],usedAssignments=new int[assignments.size()];
        for(Map<String,Object> lock:list(input,"schedule")){if(!Boolean.TRUE.equals(lock.get("locked"))||n(lock,"day",-1)==5)continue;int c=classIndex(s(lock,"className")),d=n(lock,"day",-1),p=n(lock,"period",0)-1;String teacher=s(lock,"teacher"),subject=s(lock,"subject");if(c<0||d<0||d>4||p<0||p>4||!max.containsKey(teacher))throw new IllegalArgumentException("Có tiết khóa không hợp lệ. Hãy kiểm tra lớp, giáo viên và thời gian.");int ai=-1;for(int i=0;i<assignments.size();i++){Map<String,Object>a=assignments.get(i);if(s(a,"className").equals(s(lock,"className"))&&s(a,"teacher").equals(teacher)&&s(a,"subject").equals(subject)&&usedAssignments[i]<n(a,"periods",0)){ai=i;break;}}if(ai<0||!assignmentShift(assignments.get(ai)).equals(s(lock,"shift")))throw new IllegalArgumentException("Tiết khóa không khớp phân công hoặc buổi học: "+subject+" · "+s(lock,"className"));int t=max.get(teacher),session=d+(s(lock,"shift").equals("morning")?0:6);if(teacherUnavailable(teachers.get(t),session,p))throw new IllegalArgumentException("Tiết khóa trùng thời gian nghỉ của giáo viên "+teacher+".");if(grid[c][session][p]!=-1||busy[t][session][p])throw new IllegalArgumentException("Tiết khóa bị trùng lớp, giáo viên hoặc hoạt động cố định.");grid[c][session][p]=ai;lockedGrid[c][session][p]=true;busy[t][session][p]=true;teacherLoad[t][session]++;usedAssignments[ai]++;}
        for(int c=0;c<classes.size();c++)for(int session=0;session<12;session++){int math=0,english=0;for(int p=0;p<5;p++){int ai=grid[c][session][p];if(ai<0)continue;String key=subjectKey(s(assignments.get(ai),"subject"));if(key.equals("toan"))math++;if(key.equals("anh")||key.equals("tienganh"))english++;}if(math>2||english>1)throw new IllegalArgumentException("C\u00e1c ti\u1ebft kh\u00f3a c\u1ee7a l\u1edbp "+s(classes.get(c),"name")+" v\u01b0\u1ee3t s\u1ed1 ti\u1ebft To\u00e1n ho\u1eb7c Anh trong c\u00f9ng m\u1ed9t bu\u1ed5i.");}
        for(int c=0;c<classes.size();c++){String error=literatureError(c,false);if(!error.isEmpty())throw new IllegalArgumentException(error);}
        for(int t=0;t<teachers.size();t++){int used=0;for(int load:teacherLoad[t])if(load>0)used++;if(used>maxSessions(teachers.get(t)))throw new IllegalArgumentException("Các tiết khóa khiến giáo viên "+s(teachers.get(t),"name")+" vượt số buổi đã chọn.");}
        for(int c=0;c<classes.size();c++){int off=s(classes.get(c),"shift").equals("morning")?0:6;for(int d=0;d<5;d++)for(int p=0;p<5;p++){int a=grid[c][off+d][p];if(a<0)continue;String subject=s(assignments.get(a),"subject");for(int dd=d;dd<5;dd++)for(int q=dd==d?p+1:0;q<5;q++){int b=grid[c][off+dd][q];if(b<0||!subject.equalsIgnoreCase(s(assignments.get(b),"subject")))continue;boolean adjacent=d==dd&&q-p==1;if(adjacent&&!literature(subject))throw new IllegalArgumentException("Chỉ môn Văn được xếp tiết đôi trong buổi chính: "+subject+".");if(!literature(subject)&&subjectCount(c,subject)<3&&!flexibleDays(subject)&&dd-d<2){String firstTeacher=s(assignments.get(a),"teacher"),secondTeacher=s(assignments.get(b),"teacher");boolean single=d==dd&&firstTeacher.equals(secondTeacher)&&maxSessions(teachers.get(max.get(firstTeacher)))==1;boolean doubleLiterature=adjacent&&literature(subject);if(!single&&!doubleLiterature)throw new IllegalArgumentException("Các tiết khóa của môn "+subject+" cần cách nhau ít nhất 1 ngày ở giữa.");}}}}
        for(int c=0;c<classes.size();c++){int off=s(classes.get(c),"shift").equals("morning")?0:6;for(int d=0;d<5;d++)for(int p=0;p<3;p++){int a=grid[c][off+d][p],b=grid[c][off+d][p+1],z=grid[c][off+d][p+2];if(a>=0&&b>=0&&z>=0&&literature(s(assignments.get(a),"subject"))&&s(assignments.get(a),"subject").equalsIgnoreCase(s(assignments.get(b),"subject"))&&s(assignments.get(a),"subject").equalsIgnoreCase(s(assignments.get(z),"subject")))throw new IllegalArgumentException("Môn Văn chỉ được xếp tối đa 2 tiết liên tiếp.");}}
        for(int ai=0;ai<assignments.size();ai++){Map<String,Object>a=assignments.get(ai);if(extraKind(s(a,"subject"))>0)continue;int ci=classIndex(s(a,"className"));int count=n(a,"periods",0)-usedAssignments[ai];classCount[ci]+=count;for(int j=0;j<count;j++)tasks.add(ai);}
        for(int c=0;c<classes.size();c++){int capacity=0,off=s(classes.get(c),"shift").equals("morning")?0:6;for(int d=0;d<5;d++)for(int cell:grid[c][off+d])if(cell==-1)capacity++;if(classCount[c]>capacity)throw new IllegalArgumentException("Lớp "+s(classes.get(c),"name")+" có nhiều tiết hơn khung học còn trống.");}
        Collections.shuffle(tasks,rand); tasks.sort((a,b)->Integer.compare(difficulty(b),difficulty(a)));nodes=0;
        searchExtras(tasks,0);progress.accept(attempt+1);if(bestScore==0||(untilFound&&best!=null))break;
      }
      if(best==null)return Map.of("ok",false,"message","Chưa tìm được lịch hợp lệ. Hãy kiểm tra phân công, hoạt động cố định, tiết khóa, số buổi dạy và khoảng trống giữa các tiết của giáo viên.");
      return Map.of("ok",true,"schedule",best,"score",bestScore,"message",untilFound?"Đã tìm được lịch hợp lệ. Chưa chứng minh tối ưu tuyệt đối.":"Đã tìm được lịch hợp lệ tốt nhất trong các lần thử. Chưa chứng minh tối ưu tuyệt đối.");
    }
    int difficulty(int ai){Map<String,Object>a=assignments.get(ai);return n(a,"periods",0)*10;}
    int classIndex(String name){for(int i=0;i<classes.size();i++)if(s(classes.get(i),"name").equals(name))return i;return -1;}
    void searchExtras(List<Integer> tasks,int c){
      if(++nodes>18000)return;if(c==classes.size()){search(tasks,0);return;}int first=extraPairs[c][0],second=extraPairs[c][1];if(first<0){searchExtras(tasks,c+1);return;}int off=s(classes.get(c),"shift").equals("morning")?6:0;
      List<Integer> candidates=new ArrayList<>();for(int d=0;d<5;d++)for(int order=0;order<2;order++)candidates.add(d*2+order);Collections.shuffle(candidates,rand);
      for(int choice:candidates){int session=off+choice/2;int[] expected=choice%2==0?new int[]{first,first,second,second}:new int[]{second,second,first,first};boolean ok=true;List<Integer> inserted=new ArrayList<>();
        for(int s=0;s<12;s++)for(int p=0;p<5;p++)if(lockedGrid[c][s][p]&&extraKind(Main.Scheduler.s(assignments.get(grid[c][s][p]),"subject"))>0&&(s!=session||p>=4||grid[c][s][p]!=expected[p]))ok=false;
        for(int p=0;ok&&p<4;p++){int ai=expected[p],t=max.get(s(assignments.get(ai),"teacher"));if(lockedGrid[c][session][p])continue;if(grid[c][session][p]!=-1||busy[t][session][p]||teacherUnavailable(teachers.get(t),session,p)){ok=false;break;}int used=0;for(int load:teacherLoad[t])if(load>0)used++;if(teacherLoad[t][session]==0&&used>=maxSessions(teachers.get(t))){ok=false;break;}grid[c][session][p]=ai;busy[t][session][p]=true;teacherLoad[t][session]++;inserted.add(p);}
        if(ok)searchExtras(tasks,c+1);for(int p:inserted){int t=max.get(s(assignments.get(grid[c][session][p]),"teacher"));grid[c][session][p]=-1;busy[t][session][p]=false;teacherLoad[t][session]--;}if(nodes>18000)return;
      }
    }
    void search(List<Integer> tasks,int pos){
      if(++nodes>18000)return;
      if(pos==tasks.size()){int score=score();if(score<bestScore){bestScore=score;best=snapshot();}return;}
      int ai=tasks.get(pos);Map<String,Object>a=assignments.get(ai);int c=classIndex(s(a,"className")),t=max.get(s(a,"teacher"));String shift=s(classes.get(c),"shift");int off=shift.equals("morning")?0:6;
      List<int[]> options=new ArrayList<>();
      for(int d=0;d<5;d++)for(int p=0;p<5;p++)if(grid[c][off+d][p]==-1&&!busy[t][off+d][p]&&!teacherUnavailable(teachers.get(t),off+d,p)){
        int used=0;for(int load:teacherLoad[t])if(load>0)used++;if(teacherLoad[t][off+d]==0 && used>=maxSessions(teachers.get(t)))continue;
        boolean tooClose=false;String subject=s(a,"subject");int sameSession=0;for(int q=0;q<5;q++){int other=grid[c][off+d][q];if(other>=0&&sameLimitedSubject(subject,s(assignments.get(other),"subject")))sameSession++;}if(flexibleDays(subject)&&sameSession>=(subjectKey(subject).equals("toan")?2:1))continue;int sameLiterature=0;for(int q=0;q<5;q++){int other=grid[c][off+d][q];if(other>=0&&literature(s(assignments.get(other),"subject")))sameLiterature++;}if(literature(subject)&&sameLiterature>=2)continue;for(int dd=0;dd<5;dd++)for(int q=0;q<5;q++){int other=grid[c][off+dd][q];if(other>=0&&literature(subject)&&literature(s(assignments.get(other),"subject"))){if(dd==d&&Math.abs(q-p)!=1)tooClose=true;continue;}if(other<0||!s(assignments.get(other),"subject").equalsIgnoreCase(subject))continue;boolean adjacent=dd==d&&Math.abs(q-p)==1;if(adjacent&&!literature(subject)){tooClose=true;continue;}if(subjectCount(c,subject)<3&&!flexibleDays(subject)&&Math.abs(dd-d)<2){boolean single=dd==d&&s(assignments.get(other),"teacher").equals(s(a,"teacher"))&&maxSessions(teachers.get(t))==1;boolean doubleLiterature=adjacent&&literature(subject);if(!single&&!doubleLiterature)tooClose=true;}}if(tooClose)continue;
        if(literature(subject)){boolean triple=false;for(int start=Math.max(0,p-2);start<=Math.min(p,2);start++){int matched=1;for(int q=start;q<start+3;q++){if(q==p)continue;int existing=grid[c][off+d][q];if(existing>=0&&subject.equalsIgnoreCase(s(assignments.get(existing),"subject")))matched++;}if(matched==3)triple=true;}if(triple)continue;}
        int cost=rand.nextInt(5); if(teacherLoad[t][off+d]==0)cost+=used<minSessions(teachers.get(t))?-15:12;else {int dist=5;for(int q=0;q<5;q++)if(busy[t][off+d][q])dist=Math.min(dist,Math.abs(p-q));cost+=dist*4;}
        for(int dd=0;dd<5;dd++)for(int q=0;q<5;q++){int other=grid[c][off+dd][q];if(other>=0&&s(assignments.get(other),"subject").equalsIgnoreCase(s(a,"subject"))){int diff=Math.abs(dd-d);if(diff==0)cost+=35;else if(diff<2 && subjectCount(c,s(a,"subject"))<3&&!flexibleDays(s(a,"subject")))cost+=15;}}
        options.add(new int[]{d,p,cost});
      }
      options.sort(Comparator.comparingInt(x->x[2]));int limit=Math.min(options.size(),pos<tasks.size()-4?6:options.size());
      for(int i=0;i<limit;i++){int d=options.get(i)[0],p=options.get(i)[1];grid[c][off+d][p]=ai;busy[t][off+d][p]=true;teacherLoad[t][off+d]++;search(tasks,pos+1);teacherLoad[t][off+d]--;busy[t][off+d][p]=false;grid[c][off+d][p]=-1;if(nodes>18000)return;}
    }
    int subjectCount(int c,String subject){int sum=0;for(Map<String,Object>a:assignments)if(s(a,"className").equals(s(classes.get(c),"name"))&&s(a,"subject").equalsIgnoreCase(subject))sum+=n(a,"periods",0);return sum;}
    String literatureError(int c,boolean complete){int off=s(classes.get(c),"shift").equals("morning")?0:6,singles=0,total=0;String name=s(classes.get(c),"name");for(Map<String,Object>a:assignments)if(s(a,"className").equals(name)&&literature(s(a,"subject")))total+=n(a,"periods",0);for(int day=0;day<5;day++){List<Integer> periods=new ArrayList<>();for(int p=0;p<5;p++){int ai=grid[c][off+day][p];if(ai>=0&&literature(s(assignments.get(ai),"subject")))periods.add(p);}if(periods.isEmpty())continue;if(periods.size()>2)return "Lớp "+name+" chỉ được học tối đa 2 tiết Văn trong một buổi.";if(periods.size()==2&&periods.get(1)-periods.get(0)!=1)return "Hai tiết Văn của lớp "+name+" trong cùng buổi phải liền nhau.";if(periods.size()==1)singles++;}if(complete&&total>0&&singles!=total%2)return "Các tiết Văn của lớp "+name+" phải ghép thành từng cặp liền nhau; chỉ được một tiết lẻ nếu số tiết tuần là số lẻ.";return "";}
    int score(){int score=0;for(int c=0;c<classes.size();c++)if(!literatureError(c,true).isEmpty())return Integer.MAX_VALUE;for(int c=0;c<classes.size();c++)for(int d=0;d<12;d++){int first=5,last=-1;for(int p=0;p<5;p++)if(grid[c][d][p]!=-1){first=Math.min(first,p);last=p;}for(int p=first;p<=last;p++)if(grid[c][d][p]==-1)return Integer.MAX_VALUE;}
      for(int t=0;t<teachers.size();t++){int sessions=0;for(int d=0;d<12;d++){int first=5,last=-1,previous=-1;for(int p=0;p<5;p++)if(busy[t][d][p]){if(previous>=0&&p-previous>2)return Integer.MAX_VALUE;previous=p;first=Math.min(first,p);last=p;}if(last>=0){if(teacherLoad[t][d]<2)return Integer.MAX_VALUE;sessions++;score+=(last-first+1-teacherLoad[t][d])*20;if(teacherLoad[t][d]<3)score+=(3-teacherLoad[t][d])*4;if(teacherLoad[t][d]>4)score+=8;}}if(sessions>0&&(sessions<minSessions(teachers.get(t))||sessions>maxSessions(teachers.get(t))))return Integer.MAX_VALUE;}
      for(int c=0;c<classes.size();c++){int off=s(classes.get(c),"shift").equals("morning")?0:6;for(int d=0;d<5;d++)for(int p=0;p<5;p++){int a=grid[c][off+d][p];if(a<0)continue;String sub=s(assignments.get(a),"subject");for(int dd=d;dd<5;dd++)for(int q=dd==d?p+1:0;q<5;q++){int b=grid[c][off+dd][q];if(b>=0&&s(assignments.get(b),"subject").equalsIgnoreCase(sub)){int diff=dd-d;if(diff==0)score+=20;else if(diff<2&&subjectCount(c,sub)<3&&!flexibleDays(sub))score+=10;}}}}return score;}
    List<Map<String,Object>> snapshot(){List<Map<String,Object>> out=new ArrayList<>();for(int c=0;c<classes.size();c++)for(int d=0;d<12;d++)for(int p=0;p<5;p++){int a=grid[c][d][p];String shift=d<6?"morning":"afternoon";if(a>=0){Map<String,Object>x=assignments.get(a);out.add(Map.of("className",s(classes.get(c),"name"),"shift",shift,"day",d%6,"period",p+1,"subject",s(x,"subject"),"teacher",s(x,"teacher"),"locked",lockedGrid[c][d][p]));}else if(a<=-10){Map<String,Object>x=events.get(-10-a);out.add(Map.of("className",s(classes.get(c),"name"),"shift",shift,"day",d%6,"period",p+1,"subject",s(x,"name"),"teacher",""));}}return out;}
  }
  static class Json {
    String s;int i;Json(String s){this.s=s;}void ws(){while(i<s.length()&&Character.isWhitespace(s.charAt(i)))i++;}char take(){return s.charAt(i++);}Object parse(){ws();Object x=read();ws();if(i!=s.length())throw new IllegalArgumentException("JSON không hợp lệ");return x;}
    Object read(){ws();char c=take();if(c=='{'){Map<String,Object> m=new LinkedHashMap<>();ws();if(s.charAt(i)=='}'){i++;return m;}while(true){ws();String k=(String)read();ws();if(take()!=':')throw new IllegalArgumentException("JSON không hợp lệ");m.put(k,read());ws();char end=take();if(end=='}')return m;if(end!=',')throw new IllegalArgumentException("JSON không hợp lệ");}}if(c=='['){List<Object>a=new ArrayList<>();ws();if(s.charAt(i)==']'){i++;return a;}while(true){a.add(read());ws();char end=take();if(end==']')return a;if(end!=',')throw new IllegalArgumentException("JSON không hợp lệ");}}if(c=='"'){StringBuilder b=new StringBuilder();while(i<s.length()){char x=take();if(x=='"')return b.toString();if(x=='\\'){x=take();if(x=='u'){b.append((char)Integer.parseInt(s.substring(i,i+4),16));i+=4;}else b.append(switch(x){case 'n'->'\n';case 'r'->'\r';case 't'->'\t';default->x;});}else b.append(x);}throw new IllegalArgumentException("JSON không hợp lệ");}int start=i-1;while(i<s.length()&&",]} \r\n\t".indexOf(s.charAt(i))<0)i++;String v=s.substring(start,i);if(v.equals("true"))return true;if(v.equals("false"))return false;if(v.equals("null"))return null;return Double.parseDouble(v);}
    static String stringify(Object o){if(o==null)return "null";if(o instanceof String v)return "\""+v.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";if(o instanceof Number||o instanceof Boolean)return o.toString();if(o instanceof Map<?,?> m){List<String>p=new ArrayList<>();for(var e:m.entrySet())p.add(stringify(e.getKey().toString())+":"+stringify(e.getValue()));return "{"+String.join(",",p)+"}";}if(o instanceof Iterable<?> a){List<String>p=new ArrayList<>();for(Object x:a)p.add(stringify(x));return "["+String.join(",",p)+"]";}throw new IllegalArgumentException("Không thể chuyển JSON");}
  }
}
