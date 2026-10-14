#include <bits/stdc++.h>
using namespace std;

int main() {
    unsigned long long n;
    cin >> n;
    int digits = 0, sum = 0;
    do {
        sum += n % 10;
        n /= 10;
        digits++;
    } while (n > 0);
    cout << digits << " " << sum << "\n";
}
