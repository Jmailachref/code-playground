import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(in.readLine());
        int r = Integer.parseInt(st.nextToken());
        int c = Integer.parseInt(st.nextToken());
        int k = Integer.parseInt(st.nextToken());
        int cells = r * c;
        byte[] cost = new byte[cells];
        for (int i = 0; i < r; i++) {
            String line = in.readLine().trim();
            for (int j = 0; j < c; j++) cost[i * c + j] = (byte) (line.charAt(j) - '0');
        }
        int states = cells * (k + 1);
        int[] dist = new int[states];
        Arrays.fill(dist, Integer.MAX_VALUE);
        // state = cell * (k + 1) + coupons used; edge weights are 0..9, so a circular bucket queue works
        int buckets = 10;
        IntList[] queue = new IntList[buckets];
        for (int i = 0; i < buckets; i++) queue[i] = new IntList();
        dist[0] = 0;
        queue[0].add(0);
        int pending = 1;
        int[] dr = {1, -1, 0, 0}, dc = {0, 0, 1, -1};
        for (int d = 0; pending > 0; d++) {
            IntList bucket = queue[d % buckets];
            for (int idx = 0; idx < bucket.size; idx++) {
                int s = bucket.data[idx];
                pending--;
                if (dist[s] != d) continue;
                int cell = s / (k + 1), used = s % (k + 1);
                int row = cell / c, col = cell % c;
                for (int dir = 0; dir < 4; dir++) {
                    int nr = row + dr[dir], nc = col + dc[dir];
                    if (nr < 0 || nr >= r || nc < 0 || nc >= c) continue;
                    int ncell = nr * c + nc;
                    int paid = ncell * (k + 1) + used;
                    int nd = d + cost[ncell];
                    if (nd < dist[paid]) {
                        dist[paid] = nd;
                        queue[nd % buckets].add(paid);
                        pending++;
                    }
                    if (used < k && d < dist[paid + 1]) {
                        dist[paid + 1] = d;
                        bucket.add(paid + 1);
                        pending++;
                    }
                }
            }
            bucket.size = 0;
        }
        int target = (cells - 1) * (k + 1);
        int best = Integer.MAX_VALUE;
        for (int u = 0; u <= k; u++) best = Math.min(best, dist[target + u]);
        System.out.println(best);
    }

    static final class IntList {
        int[] data = new int[16];
        int size;

        void add(int x) {
            if (size == data.length) data = Arrays.copyOf(data, size * 2);
            data[size++] = x;
        }
    }
}
