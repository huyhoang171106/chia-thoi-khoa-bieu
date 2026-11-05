import java.util.*;
public class UnlimitedSearchTest {
  static class Stop extends RuntimeException {}
  public static void main(String[] args){
    Map<String,Object> data=Map.of("classes",List.of(Map.of("name","9/1","shift","morning")),"teachers",List.of(Map.of("name","Lan","sessionRule","1")),"assignments",List.of(Map.of("className","9/1","teacher","Lan","subject","Toán","periods",2)),"events",List.of());
    int[] last={0};try{new Main.Scheduler(data,n->{last[0]=n;if(n==72)throw new Stop();},true).run();throw new AssertionError("Expected search to keep running");}catch(Stop expected){}if(last[0]!=72)throw new AssertionError("Stopped early: "+last[0]);
    Map<String,Object> possible=Map.of("classes",List.of(Map.of("name","9/1","shift","morning")),"teachers",List.of(Map.of("name","Lan","sessionRule","1")),"assignments",List.of(Map.of("className","9/1","teacher","Lan","subject","Văn","periods",2)),"events",List.of());
    last[0]=0;Map<String,Object> result=new Main.Scheduler(possible,n->last[0]=n,true).run();if(!Boolean.TRUE.equals(result.get("ok"))||last[0]!=1)throw new AssertionError(result);
    System.out.println("Search continues past 70 attempts and stops on first valid schedule.");
  }
}
