package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
)

func main() {
	reader := bufio.NewReader(os.Stdin)
	writer := bufio.NewWriter(os.Stdout)
	defer writer.Flush()
	var n int
	fmt.Fscan(reader, &n)
	iv := make([][2]int64, n)
	for i := range iv {
		fmt.Fscan(reader, &iv[i][0], &iv[i][1])
	}
	sort.Slice(iv, func(i, j int) bool {
		if iv[i][0] != iv[j][0] {
			return iv[i][0] < iv[j][0]
		}
		return iv[i][1] < iv[j][1]
	})
	var merged [][2]int64
	for _, cur := range iv {
		if k := len(merged); k > 0 && cur[0] <= merged[k-1][1] {
			if cur[1] > merged[k-1][1] {
				merged[k-1][1] = cur[1]
			}
		} else {
			merged = append(merged, cur)
		}
	}
	fmt.Fprintln(writer, len(merged))
	for _, m := range merged {
		fmt.Fprintln(writer, m[0], m[1])
	}
}
