import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class CpFixtureCheck {
  @SuppressWarnings("unchecked")
  public static void main(String[] args) throws Exception {
    Map<String,Object> data=(Map<String,Object>)new Main.Json(Files.readString(Path.of(args[0]),StandardCharsets.UTF_8)).parse();
    Map<String,Object> result=CpScheduler.run(data,ignored->{});
    System.out.println("status="+result.get("status")+", ok="+result.get("ok")+", message="+result.get("message"));
  }
}
