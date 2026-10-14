package main

import (
	"bufio"
	"fmt"
	"os"
)

func main() {
	reader := bufio.NewReader(os.Stdin)
	var r, c int
	fmt.Fscan(reader, &r, &c)
	grid := make([]string, r)
	for i := range grid {
		fmt.Fscan(reader, &grid[i])
	}
	const inf = 1 << 30
	dist := make([]int, r*c)
	for i := range dist {
		dist[i] = inf
	}
	// 0-1 BFS by levels: cur holds cells at distance level, next those at level+1.
	dist[0] = 0
	cur := []int{0}
	var next []int
	dy := [4]int{1, -1, 0, 0}
	dx := [4]int{0, 0, 1, -1}
	for level := 0; len(cur) > 0; level++ {
		for i := 0; i < len(cur); i++ {
			id := cur[i]
			if dist[id] != level {
				continue
			}
			y, x := id/c, id%c
			for d := 0; d < 4; d++ {
				ny, nx := y+dy[d], x+dx[d]
				if ny < 0 || ny >= r || nx < 0 || nx >= c {
					continue
				}
				nid := ny*c + nx
				if grid[ny][nx] == '#' {
					if level+1 < dist[nid] {
						dist[nid] = level + 1
						next = append(next, nid)
					}
				} else if level < dist[nid] {
					dist[nid] = level
					cur = append(cur, nid)
				}
			}
		}
		cur, next = next, cur[:0]
	}
	fmt.Println(dist[r*c-1])
}
