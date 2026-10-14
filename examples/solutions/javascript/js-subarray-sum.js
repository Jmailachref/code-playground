const data = require("fs").readFileSync(0, "utf8").trim().split(/\s+/).map(Number);
const n = data[0];
const k = data[1];
const seen = new Map([[0, 1]]);
let prefix = 0;
let count = 0;
for (let i = 0; i < n; i++) {
  prefix += data[2 + i];
  count += seen.get(prefix - k) || 0;
  seen.set(prefix, (seen.get(prefix) || 0) + 1);
}
console.log(String(count));
