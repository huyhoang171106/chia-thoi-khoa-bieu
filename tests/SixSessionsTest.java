import java.util.*;

public class SixSessionsTest {
  static Map<String,Object> lock(String c,String shift,int day){return Map.of("className",c,"shift",shift,"teacher","Lan","subject","Toán","day",day,"period",1,"locked",true);}
  public static void main(String[] args)throws Exception{
    Map<String,Object> input=new HashMap<>();
    input.put("classes",List.of(Map.of("name","6/1","shift","morning"),Map.of("name","7/1","shift","afternoon")));
    input.put("teachers",List.of(Map.of("name","Lan","sessionRule","6")));
    input.put("assignments",List.of(Map.of("className","6/1","teacher","Lan","subject","Toán","periods",3),Map.of("className","7/1","teacher","Lan","subject","Toán","periods",3)));
    input.put("events",List.of());List<Map<String,Object>> locked=new ArrayList<>();for(int d=0;d<3;d++){locked.add(lock("6/1","morning",d));locked.add(lock("7/1","afternoon",d));}input.put("schedule",locked);
    Map<String,Object> result=CpScheduler.run(input,ignored->{});if(!Boolean.TRUE.equals(result.get("ok")))throw new AssertionError(result);
    Set<String> sessions=new HashSet<>();for(Map<String,Object> row:Main.Scheduler.list(result,"schedule"))if("Lan".equals(row.get("teacher")))sessions.add(row.get("shift")+":"+row.get("day"));
    if(sessions.size()!=6)throw new AssertionError(sessions);
    System.out.println("Six-session teacher passes solver, locked lessons and independent validation.");
  }
}
