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
	// Suffix automaton: each state v adds length[v] - length[link[v]] new substrings.
	maxStates := 2*n + 1
	length := make([]int32, maxStates)
	link := make([]int32, maxStates)
	next := make([][26]int32, maxStates)
	for i := range next[0] {
		next[0][i] = -1
	}
	link[0] = -1
	size, last := int32(1), int32(0)
	for i := 0; i < n; i++ {
		ch := s[i] - 'a'
		cur := size
		size++
		length[cur] = length[last] + 1
		for j := range next[cur] {
			next[cur][j] = -1
		}
		p := last
		for p != -1 && next[p][ch] == -1 {
			next[p][ch] = cur
			p = link[p]
		}
		if p == -1 {
			link[cur] = 0
		} else {
			q := next[p][ch]
			if length[p]+1 == length[q] {
				link[cur] = q
			} else {
				clone := size
				size++
				length[clone] = length[p] + 1
				next[clone] = next[q]
				link[clone] = link[q]
				for p != -1 && next[p][ch] == q {
					next[p][ch] = clone
					p = link[p]
				}
				link[q] = clone
				link[cur] = clone
			}
		}
		last = cur
	}
	var total int64
	for v := int32(1); v < size; v++ {
		total += int64(length[v] - length[link[v]])
	}
	fmt.Println(total)
}
