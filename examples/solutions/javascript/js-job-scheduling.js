const data = require("fs").readFileSync(0, "utf8").trim().split(/\s+/).map(Number);
const n = data[0];
const jobs = [];
for (let i = 0; i < n; i++) jobs.push([data[1 + 3 * i], data[2 + 3 * i], data[3 + 3 * i]]);
jobs.sort((a, b) => a[1] - b[1]);
// best[i] = best profit using the first i jobs (by end time)
const best = new Array(n + 1).fill(0);
for (let i = 1; i <= n; i++) {
  const [s, , p] = jobs[i - 1];
  // number of jobs among the first i-1 whose end <= s
  let lo = 0;
  let hi = i - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (jobs[mid - 1][1] <= s) lo = mid;
    else hi = mid - 1;
  }
  best[i] = Math.max(best[i - 1], best[lo] + p);
}
console.log(String(best[n]));
