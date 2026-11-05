import java.util.*;
public class TeacherTimeOffTest {
  static Map<String,Object> input(String rule){return new HashMap<>(Map.of("classes",List.of(Map.of("name","6/1","shift","morning")),"teachers",List.of(Map.of("name","Lan","offRule",rule)),"assignments",List.of(Map.of("className","6/1","teacher","Lan","subject","Toán","periods",4)),"events",List.of()));}
  public static void main(String[] args){
    for(String rule:List.of("first","session:1:morning","day:1")){Map<String,Object> result=new Main.Scheduler(input(rule)).run();if(!Boolean.TRUE.equals(result.get("ok")))throw new AssertionError(result);for(Object o:(List<?>)result.get("schedule")){Map<?,?> x=(Map<?,?>)o;int day=((Number)x.get("day")).intValue(),period=((Number)x.get("period")).intValue();if(rule.equals("first")&&period==1||!rule.equals("first")&&day==1)throw new AssertionError(x);}}
    Map<String,Object> locked=input("first");locked.put("schedule",List.of(Map.of("className","6/1","shift","morning","day",0,"period",1,"teacher","Lan","subject","Toán","locked",true)));try{new Main.Scheduler(locked).run();throw new AssertionError("Locked lesson accepted");}catch(IllegalArgumentException expected){if(!expected.getMessage().contains("nghỉ"))throw expected;}
    if(!Main.Scheduler.teacherUnavailable(Map.of("offRule","session:2:afternoon"),8,4)||Main.Scheduler.teacherUnavailable(Map.of("offRule","session:2:afternoon"),2,4)||!Main.Scheduler.teacherUnavailable(Map.of("offRule","day:2"),2,4)||!Main.Scheduler.teacherUnavailable(Map.of("offRule","day:2"),8,4))throw new AssertionError("Shift/day mismatch");
    System.out.println("Teacher time off passed.");
  }
}
