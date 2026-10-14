import heapq
import sys


def main():
    data = sys.stdin.buffer.read().split()
    n, m = int(data[0]), int(data[1])
    after = [[] for _ in range(n + 1)]
    indegree = [0] * (n + 1)
    for i in range(m):
        a, b = int(data[2 + 2 * i]), int(data[3 + 2 * i])
        after[a].append(b)
        indegree[b] += 1
    heap = [v for v in range(1, n + 1) if indegree[v] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        v = heapq.heappop(heap)
        order.append(v)
        for w in after[v]:
            indegree[w] -= 1
            if indegree[w] == 0:
                heapq.heappush(heap, w)
    print(" ".join(map(str, order)) if len(order) == n else "IMPOSSIBLE")


main()
