import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        int n = Integer.parseInt(in.readLine().trim());
        StringTokenizer st = new StringTokenizer(in.readLine());
        long min = Long.MAX_VALUE, max = Long.MIN_VALUE, sum = 0;
        for (int i = 0; i < n; i++) {
            long x = Long.parseLong(st.nextToken());
            min = Math.min(min, x);
            max = Math.max(max, x);
            sum += x;
        }
        System.out.println(min + " " + max + " " + sum);
    }
}
