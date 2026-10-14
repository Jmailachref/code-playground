import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        String line = new Scanner(System.in).nextLine();
        StringBuilder kept = new StringBuilder();
        for (char c : line.toCharArray()) {
            if (Character.isLetterOrDigit(c)) kept.append(Character.toLowerCase(c));
        }
        String s = kept.toString();
        System.out.println(s.equals(kept.reverse().toString()) ? "YES" : "NO");
    }
}
