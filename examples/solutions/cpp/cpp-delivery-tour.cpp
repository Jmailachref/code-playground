#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    cin >> n;
    vector<vector<long long>> d(n, vector<long long>(n));
    for (auto& row : d)
        for (auto& x : row) cin >> x;
    if (n == 1) { cout << 0 << "\n"; return 0; }
    const long long INF = LLONG_MAX / 4;
    int full = 1 << n;
    vector<vector<long long>> dp(full, vector<long long>(n, INF));
    dp[1][0] = 0;
    for (int mask = 1; mask < full; mask += 2) {
        for (int u = 0; u < n; u++) {
            long long cur = dp[mask][u];
            if (cur >= INF) continue;
            for (int v = 1; v < n; v++) {
                if (mask >> v & 1) continue;
                long long nd = cur + d[u][v];
                int nm = mask | (1 << v);
                if (nd < dp[nm][v]) dp[nm][v] = nd;
            }
        }
    }
    long long best = INF;
    for (int u = 1; u < n; u++) best = min(best, dp[full - 1][u] + d[u][0]);
    cout << best << "\n";
}
