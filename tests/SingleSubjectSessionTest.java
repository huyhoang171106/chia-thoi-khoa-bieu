import java.util.*;

public class SingleSubjectSessionTest {
  static Map<String,Object> lock(int period,String subject) { return Map.of("className","9/1","shift","morning","teacher","Lan","subject",subject,"day",0,"period",period,"locked",true); }
  static Map<String,Object> input(String subject,int count) {return new HashMap<>(Map.of("classes",List.of(Map.of("name","9/1","shift","morning")),"teachers",List.of(Map.of("name","Lan","sessionRule","1")),"assignments",List.of(Map.of("className","9/1","teacher","Lan","subject",subject,"periods",count)),"events",List.of(Map.of("name","Sinh hoạt","shift","morning","day",0,"period",2))));}
  public static void main(String[] args) {
    Map<String,Object> math=input("Toán",2);math.put("schedule",List.of(lock(1,"Toán"),lock(3,"Toán")));
    List<Integer> progress=new ArrayList<>();Map<String,Object> result=new Main.Scheduler(math,progress::add).run();
    if(!Boolean.TRUE.equals(result.get("ok"))||progress.isEmpty())throw new AssertionError(result);
    Map<String,Object> three=input("Toán",3);three.put("schedule",List.of(lock(1,"Toán"),lock(3,"Toán"),lock(5,"Toán")));
    try {new Main.Scheduler(three).run();throw new AssertionError("Three math lessons accepted");} catch(IllegalArgumentException expected) {if(!expected.getMessage().contains("vượt"))throw expected;}
    Map<String,Object> english=input("Anh",2);english.put("schedule",List.of(lock(1,"Anh"),lock(3,"Anh")));
    try {new Main.Scheduler(english).run();throw new AssertionError("Two English lessons accepted");} catch(IllegalArgumentException expected) {if(!expected.getMessage().contains("vượt"))throw expected;}
    if(!Main.Scheduler.sameLimitedSubject("Anh","Tiếng Anh")||Main.Scheduler.sameLimitedSubject("Toán","Anh"))throw new AssertionError("Subject matching");
    System.out.println("Two separated math lessons allowed; three math or two English rejected.");
  }
}
