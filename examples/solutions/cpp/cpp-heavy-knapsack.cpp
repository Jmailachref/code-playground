#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    long long cap;
    cin >> n >> cap;
    vector<long long> w(n);
    vector<int> v(n);
    int total = 0;
    for (int i = 0; i < n; i++) {
        cin >> w[i] >> v[i];
        total += v[i];
    }
    // minWeight[s] = lightest set of items whose values add up to exactly s
    const long long INF = LLONG_MAX / 2;
    vector<long long> minWeight(total + 1, INF);
    minWeight[0] = 0;
    for (int i = 0; i < n; i++)
        for (int s = total; s >= v[i]; s--)
            if (minWeight[s - v[i]] + w[i] < minWeight[s]) minWeight[s] = minWeight[s - v[i]] + w[i];
    int best = 0;
    for (int s = 0; s <= total; s++)
        if (minWeight[s] <= cap) best = s;
    cout << best << "\n";
}
