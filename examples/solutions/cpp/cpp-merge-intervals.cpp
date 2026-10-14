#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    cin >> n;
    vector<pair<long long, long long>> v(n);
    for (auto& [a, b] : v) cin >> a >> b;
    sort(v.begin(), v.end());
    vector<pair<long long, long long>> merged;
    for (auto [a, b] : v) {
        if (!merged.empty() && a <= merged.back().second) merged.back().second = max(merged.back().second, b);
        else merged.push_back({a, b});
    }
    cout << merged.size() << "\n";
    for (auto [a, b] : merged) cout << a << " " << b << "\n";
}
