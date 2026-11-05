import java.util.*;
public class TeacherGapTest {
  static Map<String,Object> lock(String c,String shift,int period,String subject){return Map.of("className",c,"shift",shift,"day",0,"period",period,"teacher","Lan","subject",subject,"locked",true);}
  static Map<String,Object> fixture(String secondShift,String rule,int secondPeriod){Map<String,Object> x=new HashMap<>();x.put("classes",List.of(Map.of("name","6/1","shift","morning"),Map.of("name","6/2","shift",secondShift)));x.put("teachers",List.of(Map.of("name","Lan","sessionRule",rule)));x.put("assignments",List.of(Map.of("className","6/1","teacher","Lan","subject","Toán","periods",1),Map.of("className","6/2","teacher","Lan","subject","Văn","periods",1)));x.put("events",List.of());x.put("schedule",List.of(lock("6/1","morning",1,"Toán"),lock("6/2",secondShift,secondPeriod,"Văn")));return x;}
  public static void main(String[] args){
    if(!Boolean.TRUE.equals(new Main.Scheduler(fixture("morning","1",3)).run().get("ok")))throw new AssertionError("One free period should be allowed");
    if(Boolean.TRUE.equals(new Main.Scheduler(fixture("morning","1",4)).run().get("ok")))throw new AssertionError("Two consecutive free periods should be rejected");
    if(!Boolean.TRUE.equals(new Main.Scheduler(fixture("afternoon","2",5)).run().get("ok")))throw new AssertionError("Lunch is not a teaching-period gap");
    System.out.println("Teacher gaps: one allowed, two rejected, lunch excluded.");
  }
}
