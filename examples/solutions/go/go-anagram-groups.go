package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"
)

func main() {
	reader := bufio.NewReader(os.Stdin)
	writer := bufio.NewWriter(os.Stdout)
	defer writer.Flush()
	var n int
	fmt.Fscan(reader, &n)
	groups := map[string][]string{}
	for i := 0; i < n; i++ {
		var w string
		fmt.Fscan(reader, &w)
		b := []byte(w)
		sort.Slice(b, func(x, y int) bool { return b[x] < b[y] })
		key := string(b)
		groups[key] = append(groups[key], w)
	}
	var out [][]string
	for _, g := range groups {
		sort.Strings(g)
		out = append(out, g)
	}
	sort.Slice(out, func(i, j int) bool { return out[i][0] < out[j][0] })
	fmt.Fprintln(writer, len(out))
	for _, g := range out {
		fmt.Fprintln(writer, strings.Join(g, " "))
	}
}
