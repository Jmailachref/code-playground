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
	dist := make([][]int, r)
	for i := range dist {
		dist[i] = make([]int, c)
		for j := range dist[i] {
			dist[i][j] = -1
		}
	}
	if grid[0][0] == '.' {
		dist[0][0] = 0
		queue := [][2]int{{0, 0}}
		for len(queue) > 0 {
			y, x := queue[0][0], queue[0][1]
			queue = queue[1:]
			for _, d := range [][2]int{{1, 0}, {-1, 0}, {0, 1}, {0, -1}} {
				ny, nx := y+d[0], x+d[1]
				if ny >= 0 && ny < r && nx >= 0 && nx < c && grid[ny][nx] == '.' && dist[ny][nx] < 0 {
					dist[ny][nx] = dist[y][x] + 1
					queue = append(queue, [2]int{ny, nx})
				}
			}
		}
	}
	fmt.Println(dist[r-1][c-1])
}
