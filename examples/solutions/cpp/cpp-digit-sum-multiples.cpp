#include <bits/stdc++.h>
using namespace std;

int K;

// How many x in [0, N] have a digit sum divisible by K
long long countUpTo(long long N) {
    if (N < 0) return 0;
    string s = to_string(N);
    // ways[r] = numbers of the free (non-tight) prefixes so far with digit sum = r (mod K)
    vector<long long> ways(K, 0);
    int tightSum = 0;
    for (char c : s) {
        int d = c - '0';
        vector<long long> next(K, 0);
        for (int r = 0; r < K; r++) {
            if (!ways[r]) continue;
            for (int x = 0; x <= 9; x++) next[(r + x) % K] += ways[r];
        }
        for (int x = 0; x < d; x++) next[(tightSum + x) % K]++;
        tightSum = (tightSum + d) % K;
        ways = next;
    }
    return ways[0] + (tightSum == 0 ? 1 : 0);
}

int main() {
    long long A, B;
    cin >> A >> B >> K;
    cout << countUpTo(B) - countUpTo(A - 1) << "\n";
}
