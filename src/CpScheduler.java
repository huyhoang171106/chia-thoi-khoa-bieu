import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;

/** Runs the experimental CP-SAT worker without modifying the stored input. */
final class CpScheduler {
  private CpScheduler() {}

  @SuppressWarnings("unchecked")
  static Map<String,Object> run(Map<String,Object> input,Consumer<Map<String,Object>> progress) throws Exception {
    Process process = new ProcessBuilder("python", "-X", "utf8", "scripts/cp_scheduler.py")
        .redirectError(ProcessBuilder.Redirect.DISCARD).start();
    CompletableFuture<byte[]> output = CompletableFuture.supplyAsync(() -> {
      try { return process.getInputStream().readNBytes(2_000_001); }
      catch (IOException e) { throw new UncheckedIOException(e); }
    });
    long start = System.nanoTime();
    try {
      try(OutputStream stdin=process.getOutputStream()){
        stdin.write(Main.Json.stringify(input).getBytes(StandardCharsets.UTF_8));
      }
      while(!process.waitFor(1,TimeUnit.SECONDS)) {
        progress.accept(Map.of("type","progress","phase","search","elapsed",TimeUnit.NANOSECONDS.toSeconds(System.nanoTime()-start)));
      }
      byte[] bytes=output.get(5,TimeUnit.SECONDS);
      if(process.exitValue()!=0||bytes.length>2_000_000)throw new IOException("Không chạy được bộ xếp CP-SAT.");
      Object raw=new Main.Json(new String(bytes,StandardCharsets.UTF_8)).parse();
      if(!(raw instanceof Map<?,?>))throw new IOException("Kết quả bộ xếp không hợp lệ.");
      Map<String,Object> result=(Map<String,Object>)raw;
      if(Boolean.TRUE.equals(result.get("ok")))validate(input,result);
      return result;
    } finally {
      if(process.isAlive())process.destroyForcibly();
    }
  }

  private static void validate(Map<String,Object> input,Map<String,Object> result) throws IOException {
    List<Map<String,Object>> expected=Main.Scheduler.list(input,"assignments");
    List<Map<String,Object>> schedule=Main.Scheduler.list(result,"schedule");
    Map<List<String>,Integer> expectedCounts=new HashMap<>(),actualCounts=new HashMap<>();
    for(Map<String,Object> a:expected)expectedCounts.merge(List.of(Main.Scheduler.s(a,"className"),Main.Scheduler.s(a,"teacher"),Main.Scheduler.s(a,"subject")),Main.Scheduler.n(a,"periods",0),Integer::sum);
    List<Map<String,Object>> locks=new ArrayList<>();
    for(Map<String,Object> lesson:schedule){if(Main.Scheduler.s(lesson,"teacher").isEmpty())continue;actualCounts.merge(List.of(Main.Scheduler.s(lesson,"className"),Main.Scheduler.s(lesson,"teacher"),Main.Scheduler.s(lesson,"subject")),1,Integer::sum);Map<String,Object> lock=new HashMap<>(lesson);lock.put("locked",true);locks.add(lock);}
    if(!expectedCounts.equals(actualCounts))throw new IOException("Kết quả xếp lịch không đủ hoặc thừa tiết so với phân công.");
    Map<String,Object> check=new HashMap<>(input);check.put("schedule",locks);
    try{
      Map<String,Object> checked=new Main.Scheduler(check,ignored->{},false,1).run();
      if(!Boolean.TRUE.equals(checked.get("ok")))throw new IOException("Kết quả không vượt qua bước kiểm tra quy định.");
      Set<List<Object>> actual=new HashSet<>(),verified=new HashSet<>();
      for(Map<String,Object> lesson:schedule)actual.add(slot(lesson));
      for(Map<String,Object> lesson:Main.Scheduler.list(checked,"schedule"))verified.add(slot(lesson));
      if(actual.size()!=schedule.size()||!actual.equals(verified))throw new IOException("Kết quả không khớp hoạt động cố định hoặc tiết đã xếp.");
      for(Map<String,Object> old:Main.Scheduler.list(input,"schedule"))if(Boolean.TRUE.equals(old.get("locked"))&&Main.Scheduler.n(old,"day",-1)!=5&&!actual.contains(slot(old)))throw new IOException("Kết quả không giữ nguyên tiết đã khóa.");
    }catch(IllegalArgumentException ex){throw new IOException("Kết quả không vượt qua bước kiểm tra quy định: "+ex.getMessage(),ex);}
  }

  private static List<Object> slot(Map<String,Object> x){return List.of(Main.Scheduler.s(x,"className"),Main.Scheduler.s(x,"shift"),Main.Scheduler.n(x,"day",-1),Main.Scheduler.n(x,"period",0),Main.Scheduler.s(x,"subject"),Main.Scheduler.s(x,"teacher"));}
}
