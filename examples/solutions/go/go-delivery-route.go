package main

import (
	"bufio"
	"fmt"
	"os"
)

func main() {
	reader := bufio.NewReader(os.Stdin)
	var n int
	fmt.Fscan(reader, &n)
	d := make([][]int64, n)
	for i := range d {
		d[i] = make([]int64, n)
		for j := range d[i] {
			fmt.Fscan(reader, &d[i][j])
		}
	}
	if n == 1 {
		fmt.Println(0)
		return
	}
	const inf = int64(1) << 62
	full := 1 << n
	// dp[mask][v]: cheapest walk from stop 0 visiting exactly mask (contains 0 and v), ending at v.
	dp := make([]int64, full*n)
	for i := range dp {
		dp[i] = inf
	}
	dp[1*n+0] = 0
	for mask := 1; mask < full; mask += 2 {
		for v := 0; v < n; v++ {
			cur := dp[mask*n+v]
			if cur == inf {
				continue
			}
			for u := 1; u < n; u++ {
				if mask&(1<<u) != 0 {
					continue
				}
				nm := mask | 1<<u
				if c := cur + d[v][u]; c < dp[nm*n+u] {
					dp[nm*n+u] = c
				}
			}
		}
	}
	best := inf
	for v := 1; v < n; v++ {
		if c := dp[(full-1)*n+v] + d[v][0]; c < best {
			best = c
		}
	}
	fmt.Println(best)
}
