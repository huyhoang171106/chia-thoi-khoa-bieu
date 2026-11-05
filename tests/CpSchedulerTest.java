import java.util.*;

public class CpSchedulerTest {
  static Map<String,Object> input(int sessions){return Map.of(
    "classes",List.of(Map.of("name","9/1","shift","morning")),
    "teachers",List.of(Map.of("name","Lan","sessionRule",String.valueOf(sessions))),
    "assignments",sessions==1?List.of(Map.of("className","9/1","teacher","Lan","subject","Toán","periods",3)):
      List.of(Map.of("className","9/1","teacher","Lan","subject","Toán","periods",2),Map.of("className","9/1","teacher","Lan","subject","Sử","periods",2)),
    "events",List.of());}
  public static void main(String[] args)throws Exception {
    Map<String,Object> feasible=CpScheduler.run(input(2),ignored->{});
    if(!Boolean.TRUE.equals(feasible.get("ok")))throw new AssertionError(feasible);
    Map<String,Object> impossible=CpScheduler.run(input(1),ignored->{});
    if(!"infeasible".equals(impossible.get("status"))||!String.valueOf(impossible.get("message")).contains("Lan"))throw new AssertionError(impossible);
    System.out.println("CP-SAT worker, independent validation and conflict report passed.");
  }
}
