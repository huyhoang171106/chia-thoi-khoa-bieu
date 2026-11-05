import java.util.*;

public class SchedulerRegressionTest {
  static Map<String,Object> assignment(String subject,Object periods){return Map.of("className","9/1","teacher","Lan","subject",subject,"periods",periods);}
  static Map<String,Object> lock(String subject,int period){return Map.of("className","9/1","teacher","Lan","subject",subject,"shift","morning","day",0,"period",period,"locked",true);}
  static Map<String,Object> fixture(List<Map<String,Object>> assignments){return new HashMap<>(Map.of("classes",List.of(Map.of("name","9/1","shift","morning")),"teachers",List.of(Map.of("name","Lan","sessionRule","1")),"assignments",assignments,"events",List.of()));}
  public static void main(String[] args)throws Exception{
    for(String alias:List.of("Toan","Toa\u0301n"," TOÁN ")){
      Map<String,Object> input=fixture(List.of(assignment("Toán",1),assignment(alias,1)));
      input.put("schedule",List.of(lock("Toán",1),lock(alias,2)));
      try{new Main.Scheduler(input).run();throw new AssertionError("Adjacent aliases accepted");}catch(IllegalArgumentException ex){if(!ex.getMessage().contains("tiết đôi"))throw ex;}
      if(!"infeasible".equals(CpScheduler.run(input,ignored->{}).get("status")))throw new AssertionError("CP accepted adjacent aliases");
      input.put("schedule",List.of(lock("Toán",1),lock(alias,3)));
      input.put("events",List.of(Map.of("name","Sinh hoạt","shift","morning","day",0,"period",2)));
      if(!Boolean.TRUE.equals(CpScheduler.run(input,ignored->{}).get("ok")))throw new AssertionError("Spaced aliases rejected");
    }
    for(Object value:List.of(2.5,"2.5",0,31,true)){
      Map<String,Object> input=fixture(List.of(assignment("Văn",value)));
      try{new Main.Scheduler(input).run();throw new AssertionError("Invalid periods accepted: "+value);}catch(IllegalArgumentException ex){if(!ex.getMessage().contains("số nguyên"))throw ex;}
      Map<String,Object> result=CpScheduler.run(input,ignored->{});
      if(!"error".equals(result.get("status"))||!result.get("message").toString().contains("số nguyên"))throw new AssertionError(result);
    }
    System.out.println("Canonical subject constraints and integer periods passed both schedulers.");
  }
}
