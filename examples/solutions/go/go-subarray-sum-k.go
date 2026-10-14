package main

import (
	"bufio"
	"fmt"
	"os"
)

func main() {
	reader := bufio.NewReader(os.Stdin)
	var n int
	var k int64
	fmt.Fscan(reader, &n, &k)
	seen := make(map[int64]int64, n+1)
	seen[0] = 1
	var prefix, count int64
	for i := 0; i < n; i++ {
		var x int64
		fmt.Fscan(reader, &x)
		prefix += x
		count += seen[prefix-k]
		seen[prefix]++
	}
	fmt.Println(count)
}
