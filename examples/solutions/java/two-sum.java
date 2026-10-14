import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer first = new StringTokenizer(in.readLine());
        int n = Integer.parseInt(first.nextToken());
        long target = Long.parseLong(first.nextToken());
        StringTokenizer nums = new StringTokenizer(in.readLine());
        Map<Long, Integer> seen = new HashMap<>();
        for (int j = 0; j < n; j++) {
            long x = Long.parseLong(nums.nextToken());
            Integer i = seen.get(target - x);
            if (i != null) {
                System.out.println(i + " " + j);
                return;
            }
            seen.putIfAbsent(x, j);
        }
        System.out.println(-1);
    }
}
