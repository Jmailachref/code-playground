#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    cin >> n;
    map<string, vector<string>> groups;
    for (int i = 0; i < n; i++) {
        string w;
        cin >> w;
        string key = w;
        sort(key.begin(), key.end());
        groups[key].push_back(w);
    }
    vector<vector<string>> out;
    for (auto& [k, g] : groups) {
        sort(g.begin(), g.end());
        out.push_back(g);
    }
    sort(out.begin(), out.end(), [](const auto& a, const auto& b) { return a[0] < b[0]; });
    for (auto& g : out) {
        for (size_t i = 0; i < g.size(); i++) cout << g[i] << (i + 1 == g.size() ? "\n" : " ");
    }
}
