import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        DataInputStream in = new DataInputStream(new BufferedInputStream(System.in, 1 << 16));
        int n = nextInt(in), m = nextInt(in);
        int[] eu = new int[m], ev = new int[m];
        int[] deg = new int[n + 1];
        for (int i = 0; i < m; i++) {
            eu[i] = nextInt(in);
            ev[i] = nextInt(in);
            deg[eu[i]]++;
            deg[ev[i]]++;
        }
        int[] start = new int[n + 2];
        for (int v = 1; v <= n; v++) start[v + 1] = start[v] + deg[v];
        int[] fill = Arrays.copyOf(start, n + 2);
        int[] to = new int[2 * m], id = new int[2 * m];
        for (int i = 0; i < m; i++) {
            to[fill[eu[i]]] = ev[i]; id[fill[eu[i]]++] = i;
            to[fill[ev[i]]] = eu[i]; id[fill[ev[i]]++] = i;
        }
        int[] tin = new int[n + 1], low = new int[n + 1], parentEdge = new int[n + 1], it = new int[n + 1];
        int[] stack = new int[n + 1];
        boolean[] bridge = new boolean[m];
        int timer = 0;
        for (int root = 1; root <= n; root++) {
            if (tin[root] != 0) continue;
            int sp = 0;
            stack[sp++] = root;
            parentEdge[root] = -1;
            tin[root] = low[root] = ++timer;
            it[root] = start[root];
            while (sp > 0) {
                int v = stack[sp - 1];
                if (it[v] < start[v + 1]) {
                    int k = it[v]++;
                    if (id[k] == parentEdge[v]) continue;
                    int w = to[k];
                    if (tin[w] == 0) {
                        parentEdge[w] = id[k];
                        tin[w] = low[w] = ++timer;
                        it[w] = start[w];
                        stack[sp++] = w;
                    } else {
                        low[v] = Math.min(low[v], tin[w]);
                    }
                } else {
                    sp--;
                    if (sp > 0) {
                        int p = stack[sp - 1];
                        low[p] = Math.min(low[p], low[v]);
                        if (low[v] > tin[p]) bridge[parentEdge[v]] = true;
                    }
                }
            }
        }
        List<long[]> found = new ArrayList<>();
        for (int i = 0; i < m; i++) {
            if (bridge[i]) found.add(new long[]{Math.min(eu[i], ev[i]), Math.max(eu[i], ev[i])});
        }
        found.sort((a, b) -> a[0] != b[0] ? Long.compare(a[0], b[0]) : Long.compare(a[1], b[1]));
        StringBuilder out = new StringBuilder();
        out.append(found.size()).append('\n');
        for (long[] e : found) out.append(e[0]).append(' ').append(e[1]).append('\n');
        System.out.print(out);
    }

    private static int nextInt(DataInputStream in) throws IOException {
        int c = in.read();
        while (c < '0') c = in.read();
        int x = 0;
        while (c >= '0') {
            x = x * 10 + (c - '0');
            c = in.read();
        }
        return x;
    }
}
