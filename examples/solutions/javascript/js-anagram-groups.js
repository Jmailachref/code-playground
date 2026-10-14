const words = require("fs").readFileSync(0, "utf8").trim().split("\n").slice(1).map((w) => w.trim());
const groups = new Map();
for (const w of words) {
  const key = [...w].sort().join("");
  if (!groups.has(key)) groups.set(key, new Set());
  groups.get(key).add(w);
}
const out = [...groups.values()].map((s) => [...s].sort());
out.sort((a, b) => b.length - a.length || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
console.log(out.map((g) => g.join(" ")).join("\n"));
