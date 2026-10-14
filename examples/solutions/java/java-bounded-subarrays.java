import java.io.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        StringTokenizer st = new StringTokenizer(in.readLine());
        int n = Integer.parseInt(st.nextToken());
        long s = Long.parseLong(st.nextToken());
        int[] a = new int[n];
        st = new StringTokenizer(in.readLine());
        for (int i = 0; i < n; i++) a[i] = Integer.parseInt(st.nextToken());
        long count = 0, sum = 0;
        int left = 0;
        for (int right = 0; right < n; right++) {
            sum += a[right];
            while (left <= right && sum > s) sum -= a[left++];
            count += right - left + 1;
        }
        System.out.println(count);
    }
}
