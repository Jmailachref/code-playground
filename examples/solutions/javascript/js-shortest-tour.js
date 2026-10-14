const data = require("fs").readFileSync(0, "utf8").trim().split(/\s+/).map(Number);
const n = data[0];
const d = (i, j) => data[1 + i * n + j];
// dp[mask * n + last]: cheapest path that starts at city 0, visits exactly the
// cities in mask (which always contains 0) and ends at last.
const full = 1 << n;
const dp = new Float64Array(full * n).fill(Infinity);
dp[1 * n + 0] = 0;
for (let mask = 1; mask < full; mask += 2) {
  for (let last = 0; last < n; last++) {
    const cur = dp[mask * n + last];
    if (cur === Infinity) continue;
    for (let nxt = 1; nxt < n; nxt++) {
      if (mask & (1 << nxt)) continue;
      const nm = mask | (1 << nxt);
      const cand = cur + d(last, nxt);
      if (cand < dp[nm * n + nxt]) dp[nm * n + nxt] = cand;
    }
  }
}
let ans = Infinity;
for (let last = 1; last < n; last++) ans = Math.min(ans, dp[(full - 1) * n + last] + d(last, 0));
console.log(String(ans));
