import sys
from bisect import bisect_right


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    jobs = sorted(
        (int(data[2 + 3 * i]), int(data[1 + 3 * i]), int(data[3 + 3 * i])) for i in range(n)
    )  # (end, start, weight)
    ends = [e for e, _, _ in jobs]
    best = [0] * (n + 1)  # best[i]: best total using the first i jobs by end time
    for i, (end, start, weight) in enumerate(jobs):
        j = bisect_right(ends, start, 0, i)
        best[i + 1] = max(best[i], best[j] + weight)
    print(best[n])


main()
