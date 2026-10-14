package main

import (
	"bufio"
	"fmt"
	"os"
)

func main() {
	reader := bufio.NewReader(os.Stdin)
	var s string
	fmt.Fscan(reader, &s)
	n := len(s)
	// cuts[i] = fewest cuts for the prefix s[:i]; cuts[0] = -1.
	cuts := make([]int, n+1)
	for i := range cuts {
		cuts[i] = i - 1
	}
	for center := 0; center < n; center++ {
		// odd length
		for l, r := center, center; l >= 0 && r < n && s[l] == s[r]; l, r = l-1, r+1 {
			if cuts[l]+1 < cuts[r+1] {
				cuts[r+1] = cuts[l] + 1
			}
		}
		// even length
		for l, r := center, center+1; l >= 0 && r < n && s[l] == s[r]; l, r = l-1, r+1 {
			if cuts[l]+1 < cuts[r+1] {
				cuts[r+1] = cuts[l] + 1
			}
		}
	}
	fmt.Println(cuts[n])
}
