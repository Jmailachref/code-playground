const words = require("fs").readFileSync(0, "utf8").toLowerCase().split(/\s+/).filter(Boolean);
const counts = new Map();
for (const w of words) counts.set(w, (counts.get(w) || 0) + 1);
const top = [...counts].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, 3);
console.log(top.map(([w, n]) => `${w} ${n}`).join("\n"));
