const lines = require("fs").readFileSync(0, "utf8").trim().split("\n");
const n = Number(lines[0]);
const numbers = n > 0 ? lines[1].trim().split(/\s+/).map(Number) : [];
let count = 0;
let sum = 0;
for (const x of numbers) {
  if (x % 2 === 0) {
    count++;
    sum += x;
  }
}
console.log(`${count} ${sum}`);
