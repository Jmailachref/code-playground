#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    long long k;
    cin >> n >> k;
    unordered_map<long long, int> seen;
    seen.reserve(2 * n + 2);
    seen[0] = 1;
    long long prefix = 0, count = 0;
    for (int i = 0; i < n; i++) {
        long long x;
        cin >> x;
        prefix += x;
        auto it = seen.find(prefix - k);
        if (it != seen.end()) count += it->second;
        seen[prefix]++;
    }
    cout << count << "\n";
}
