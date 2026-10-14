const data = require("fs").readFileSync(0, "utf8").trim().split(/\s+/).map(Number);
const n = data[0];
const t = data.slice(1, n + 1);
const ans = new Array(n).fill(0);
const stack = [];
for (let i = 0; i < n; i++) {
  while (stack.length && t[stack[stack.length - 1]] < t[i]) {
    const j = stack.pop();
    ans[j] = i - j;
  }
  stack.push(i);
}
console.log(ans.join(" "));
