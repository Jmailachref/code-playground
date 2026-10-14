import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        int n = Integer.parseInt(in.readLine().trim());
        int[][] d = new int[n][n];
        for (int i = 0; i < n; i++) {
            StringTokenizer st = new StringTokenizer(in.readLine());
            for (int j = 0; j < n; j++) d[i][j] = Integer.parseInt(st.nextToken());
        }
        if (n == 1) {
            System.out.println(0);
            return;
        }
        int full = 1 << n;
        final int INF = Integer.MAX_VALUE / 2;
        // dp[mask][v]: cheapest walk from 0 through exactly the cities in mask, ending at v
        int[][] dp = new int[full][n];
        for (int[] row : dp) Arrays.fill(row, INF);
        dp[1][0] = 0;
        for (int mask = 1; mask < full; mask += 2) {
            for (int v = 0; v < n; v++) {
                int cur = dp[mask][v];
                if (cur >= INF) continue;
                for (int w = 1; w < n; w++) {
                    if ((mask & (1 << w)) != 0) continue;
                    int nm = mask | (1 << w);
                    int cand = cur + d[v][w];
                    if (cand < dp[nm][w]) dp[nm][w] = cand;
                }
            }
        }
        long best = Long.MAX_VALUE;
        for (int v = 1; v < n; v++) best = Math.min(best, (long) dp[full - 1][v] + d[v][0]);
        System.out.println(best);
    }
}
