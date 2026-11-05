import java.util.*;

public class NoClosedDaysTest {
  public static void main(String[] args) {
    Map<String,Object> input = new HashMap<>();
    input.put("classes", List.of(Map.of("name", "6/1", "shift", "morning")));
    input.put("teachers", List.of(Map.of("name", "Lan", "maxSessions", 6)));
    input.put("assignments", List.of(Map.of("className", "6/1", "subject", "Toán", "teacher", "Lan", "periods", 4),Map.of("className","6/1","teacher","Lan","subject","Sử","periods",4)));
    input.put("events", List.of(Map.of("name", "Chào cờ", "shift", "morning", "day", 0, "period", 1)));
    input.put("closed", List.of("morning:0", "morning:1", "morning:2", "morning:3", "morning:4", "morning:5"));
    Map<String,Object> result = new Main.Scheduler(input,ignored->{},true).run();
    if (!Boolean.TRUE.equals(result.get("ok"))) throw new AssertionError("Legacy closed days affected scheduling");
    List<?> schedule = (List<?>) result.get("schedule");
    if (schedule.stream().noneMatch(x -> "Chào cờ".equals(((Map<?,?>)x).get("subject")))) throw new AssertionError("Fixed activity missing");
    String cleaned = Main.cleanState("{\"closed\":[\"morning:0\"],\"term\":\"HK1\"}");
    if (cleaned.contains("closed") || !cleaned.contains("HK1")) throw new AssertionError("Legacy state not cleaned");
    System.out.println("Legacy closed days ignored; fixed activities preserved");
  }
}
