public class TeacherIdentityTest {
 public static void main(String[] args){
  Main.validateTeacherNames("{\"teachers\":[{\"name\":\"Cô Lan\"},{\"name\":\"Cô Lân\"},{\"name\":\"\"}]}");
  try{Main.validateTeacherNames("{\"teachers\":[{\"name\":\"Cô Lan\"},{\"name\":\"  cô   lan \"}]}");throw new AssertionError("duplicate names accepted");}catch(IllegalArgumentException expected){}
  System.out.println("Teacher names are unique while distinct accented names remain separate.");
 }
}
