import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        int n = Integer.parseInt(in.readLine().trim());
        Map<String, List<String>> groups = new HashMap<>();
        int read = 0;
        while (read < n) {
            StringTokenizer st = new StringTokenizer(in.readLine());
            while (st.hasMoreTokens()) {
                String w = st.nextToken();
                char[] k = w.toCharArray();
                Arrays.sort(k);
                groups.computeIfAbsent(new String(k), x -> new ArrayList<>()).add(w);
                read++;
            }
        }
        List<List<String>> all = new ArrayList<>(groups.values());
        for (List<String> g : all) Collections.sort(g);
        all.sort((a, b) -> a.size() != b.size() ? b.size() - a.size() : a.get(0).compareTo(b.get(0)));
        StringBuilder out = new StringBuilder();
        for (List<String> g : all) out.append(String.join(" ", g)).append('\n');
        System.out.print(out);
    }
}
