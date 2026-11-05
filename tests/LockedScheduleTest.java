import java.util.*;

public class LockedScheduleTest {
  static Map<String,Object> input() {
    Map<String,Object> x=new HashMap<>();x.put("classes",List.of(Map.of("name","9/1","shift","morning"),Map.of("name","9/2","shift","morning")));x.put("teachers",List.of(Map.of("name","Lan","sessionRule","3")));x.put("assignments",List.of(Map.of("className","9/1","teacher","Lan","subject","Toán","periods",3),Map.of("className","9/2","teacher","Lan","subject","Văn","periods",1),Map.of("className","9/1","teacher","Lan","subject","Sử","periods",3)));x.put("events",List.of());return x;
  }
  static Map<String,Object> lock(String c,int d,int p,String subject){return Map.of("className",c,"shift","morning","teacher","Lan","subject",subject,"day",d,"period",p,"locked",true);}
  public static void main(String[] args){
    Map<String,Object> x=input();x.put("schedule",List.of(lock("9/1",0,2,"Toán")));Map<String,Object> result=new Main.Scheduler(x).run();if(!Boolean.TRUE.equals(result.get("ok")))throw new AssertionError(result);
    List<?> out=(List<?>)result.get("schedule");long matches=out.stream().map(y->(Map<?,?>)y).filter(y->Boolean.TRUE.equals(y.get("locked"))&&Integer.valueOf(0).equals(y.get("day"))&&Integer.valueOf(2).equals(y.get("period"))&&"Toán".equals(y.get("subject"))).count();if(matches!=1||out.size()!=7)throw new AssertionError("Locked lesson not preserved or duplicated: "+out);
    x.put("schedule",List.of(lock("9/1",0,2,"Toán"),lock("9/2",0,2,"Văn")));try{new Main.Scheduler(x).run();throw new AssertionError("Teacher collision accepted");}catch(IllegalArgumentException expected){}
    x.put("schedule",List.of(lock("9/1",0,2,"Văn")));try{new Main.Scheduler(x).run();throw new AssertionError("Unassigned locked lesson accepted");}catch(IllegalArgumentException expected){}
    System.out.println("Locked lessons preserved; teacher collisions and invalid assignments rejected.");
  }
}
