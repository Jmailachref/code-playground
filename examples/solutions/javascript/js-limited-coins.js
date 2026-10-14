const data = require("fs").readFileSync(0, "utf8").trim().split(/\s+/).map(Number);
const n = data[0];
const s = data[1];
// Split each coin type into packs of 1, 2, 4, ... coins so that every count
// 0..c can be formed, then run a 0/1 knapsack minimising the number of coins.
const INF = 1e9;
const best = new Int32Array(s + 1).fill(INF);
best[0] = 0;
for (let i = 0; i < n; i++) {
  const value = data[2 + 2 * i];
  let count = data[3 + 2 * i];
  for (let pack = 1; count > 0; pack *= 2) {
    const take = Math.min(pack, count);
    count -= take;
    const w = take * value;
    for (let t = s; t >= w; t--) {
      const cand = best[t - w] + take;
      if (cand < best[t]) best[t] = cand;
    }
  }
}
console.log(best[s] >= INF ? "-1" : String(best[s]));
