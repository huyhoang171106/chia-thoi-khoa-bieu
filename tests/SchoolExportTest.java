import java.nio.file.*;
import java.util.*;

public class SchoolExportTest {
  static Map<String,Object> lesson(String c,String shift,int day,int period,String subject,String teacher){return Map.of("className",c,"shift",shift,"day",day,"period",period,"subject",subject,"teacher",teacher);}
  public static void main(String[] args)throws Exception{
    Map<String,Object> state=new HashMap<>();state.put("term","Học kỳ I & II");
    state.put("classes",List.of(Map.of("name","6/10","shift","morning"),Map.of("name","6/2","shift","morning","grade","6"),Map.of("name","7A1","shift","afternoon"),Map.of("name","Khác","shift","morning")));
    state.put("events",List.of(Map.of("name","Chào cờ","shift","morning","day",0,"period",1)));
    state.put("schedule",List.of(lesson("6/2","morning",0,2,"Toán & Lý","Cô <Lan>"),lesson("6/2","afternoon",2,4,"Thể dục","Thầy An"),lesson("7A1","afternoon",4,5,"=1+1","Giáo viên"),lesson("6/10","morning",0,1,"Chào cờ","")));
    byte[] xlsx=SchoolExport.create(state);Files.createDirectories(Path.of("build"));Files.write(Path.of("build/test-school-export.xlsx"),xlsx);
    @SuppressWarnings("unchecked") List<List<String>> parsed=(List<List<String>>)Main.Xlsx.read(xlsx);if(!parsed.get(3).get(2).startsWith("6/2")||!parsed.get(5).get(2).equals("Toán & Lý\nCô <Lan>"))throw new AssertionError("Generated workbook could not be read back");
    Map<String,Object> duplicate=new HashMap<>(state);duplicate.put("schedule",List.of(lesson("6/2","morning",0,2,"Toán","Lan"),lesson("6/2","morning",0,2,"Văn","Mai")));try{SchoolExport.create(duplicate);throw new AssertionError("Duplicate slot accepted");}catch(IllegalArgumentException expected){}
    System.out.println("Workbook created; invalid duplicate slots rejected.");
  }
}
