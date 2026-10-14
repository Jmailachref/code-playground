import java.io.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        char[] s = in.readLine().trim().toCharArray();
        int n = s.length;
        // best[i] = fewest pieces for the prefix of length i
        int[] best = new int[n + 1];
        for (int i = 0; i <= n; i++) best[i] = i;
        for (int center = 0; center < n; center++) {
            for (int l = center, r = center; l >= 0 && r < n && s[l] == s[r]; l--, r++) {
                best[r + 1] = Math.min(best[r + 1], best[l] + 1);
            }
            for (int l = center, r = center + 1; l >= 0 && r < n && s[l] == s[r]; l--, r++) {
                best[r + 1] = Math.min(best[r + 1], best[l] + 1);
            }
        }
        System.out.println(best[n] - 1);
    }
}
