import java.util.*;

public class LiteratureRulesTest {
  static Map<String,Object> lock(int day,int period,String subject){return Map.of("className","6/1","shift","morning","teacher","Lan","subject",subject,"day",day,"period",period,"locked",true);}
  static Map<String,Object> input(List<Map<String,Object>> schedule){Map<String,Object> state=new HashMap<>();state.put("classes",List.of(Map.of("name","6/1","shift","morning")));state.put("teachers",List.of(Map.of("name","Lan","sessionRule","2")));state.put("assignments",List.of(Map.of("className","6/1","teacher","Lan","subject","Văn","periods",2),Map.of("className","6/1","teacher","Lan","subject","Ngữ văn","periods",2)));state.put("events",List.of());state.put("schedule",schedule);return state;}
  static void rejected(Map<String,Object> state,String message){try{new Main.Scheduler(state).run();throw new AssertionError("Invalid locked literature accepted");}catch(IllegalArgumentException ex){if(!ex.getMessage().contains(message))throw ex;}}
  public static void main(String[] args)throws Exception{
    Map<String,Object> valid=input(List.of(lock(0,1,"Văn"),lock(0,2,"Văn"),lock(1,1,"Ngữ văn"),lock(1,2,"Ngữ văn")));
    Map<String,Object> result=CpScheduler.run(valid,ignored->{});if(!Boolean.TRUE.equals(result.get("ok")))throw new AssertionError(result);
    rejected(input(List.of(lock(0,1,"Văn"),lock(0,3,"Ngữ văn"))),"liền nhau");
    System.out.println("Literature pairs, consecutive days, subject aliases and locked lessons passed.");
  }
}
