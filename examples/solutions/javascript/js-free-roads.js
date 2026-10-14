const data = require("fs").readFileSync(0, "utf8").trim().split(/\s+/).map(Number);
let pos = 0;
const n = data[pos++];
const m = data[pos++];
const k = data[pos++];
const head = new Int32Array(n + 1).fill(-1);
const next = new Int32Array(2 * m);
const to = new Int32Array(2 * m);
const wt = new Float64Array(2 * m);
let ec = 0;
const addEdge = (u, v, w) => {
  to[ec] = v;
  wt[ec] = w;
  next[ec] = head[u];
  head[u] = ec++;
};
for (let i = 0; i < m; i++) {
  const u = data[pos++];
  const v = data[pos++];
  const w = data[pos++];
  addEdge(u, v, w);
  addEdge(v, u, w);
}
const layers = k + 1;
const id = (v, j) => v * layers + j;
const dist = new Float64Array((n + 1) * layers).fill(Infinity);
// min-heap of [distance, state]
const hd = [];
const hs = [];
const push = (d, s) => {
  let i = hd.length;
  hd.push(d);
  hs.push(s);
  while (i > 0) {
    const p = (i - 1) >> 1;
    if (hd[p] <= d) break;
    hd[i] = hd[p];
    hs[i] = hs[p];
    i = p;
  }
  hd[i] = d;
  hs[i] = s;
};
const pop = () => {
  const d = hd[0];
  const s = hs[0];
  const ld = hd.pop();
  const ls = hs.pop();
  const len = hd.length;
  if (len) {
    let i = 0;
    for (;;) {
      const l = 2 * i + 1;
      if (l >= len) break;
      const r = l + 1;
      const c = r < len && hd[r] < hd[l] ? r : l;
      if (hd[c] >= ld) break;
      hd[i] = hd[c];
      hs[i] = hs[c];
      i = c;
    }
    hd[i] = ld;
    hs[i] = ls;
  }
  return [d, s];
};
dist[id(1, 0)] = 0;
push(0, id(1, 0));
while (hd.length) {
  const [d, s] = pop();
  if (d > dist[s]) continue;
  const v = Math.floor(s / layers);
  const j = s % layers;
  for (let e = head[v]; e !== -1; e = next[e]) {
    const u = to[e];
    const s1 = id(u, j);
    if (d + wt[e] < dist[s1]) {
      dist[s1] = d + wt[e];
      push(dist[s1], s1);
    }
    if (j < k) {
      const s2 = id(u, j + 1);
      if (d < dist[s2]) {
        dist[s2] = d;
        push(d, s2);
      }
    }
  }
}
let best = Infinity;
for (let j = 0; j <= k; j++) best = Math.min(best, dist[id(n, j)]);
console.log(best === Infinity ? "-1" : String(best));
