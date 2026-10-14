const lines = require("fs").readFileSync(0, "utf8").trim().split("\n");
const numbers = lines[1].trim().split(/\s+/).map(Number);
console.log(numbers.reduce((a, b) => Math.max(a, b)));
