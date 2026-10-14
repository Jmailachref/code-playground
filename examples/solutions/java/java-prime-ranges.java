import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        int q = Integer.parseInt(in.readLine().trim());
        int[] lo = new int[q], hi = new int[q];
        int maxR = 1;
        for (int i = 0; i < q; i++) {
            StringTokenizer st = new StringTokenizer(in.readLine());
            lo[i] = Integer.parseInt(st.nextToken());
            hi[i] = Integer.parseInt(st.nextToken());
            maxR = Math.max(maxR, hi[i]);
        }
        boolean[] composite = new boolean[maxR + 1];
        composite[0] = true;
        composite[1] = true;
        for (long p = 2; p * p <= maxR; p++) {
            if (!composite[(int) p]) {
                for (long m = p * p; m <= maxR; m += p) composite[(int) m] = true;
            }
        }
        int[] prefix = new int[maxR + 1];
        for (int i = 1; i <= maxR; i++) prefix[i] = prefix[i - 1] + (composite[i] ? 0 : 1);
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < q; i++) out.append(prefix[hi[i]] - prefix[lo[i] - 1]).append('\n');
        System.out.print(out);
    }
}
