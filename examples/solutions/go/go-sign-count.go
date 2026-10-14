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
	pos, neg, zero := 0, 0, 0
	for i := 0; i < n; i++ {
		var x int64
		fmt.Fscan(reader, &x)
		switch {
		case x > 0:
			pos++
		case x < 0:
			neg++
		default:
			zero++
		}
	}
	fmt.Println(pos, neg, zero)
}
