import heapq
import sys


def main():
    data = sys.stdin.buffer.read().split()
    n, m, k = int(data[0]), int(data[1]), int(data[2])
    adj = [[] for _ in range(n + 1)]
    p = 3
    for _ in range(m):
        a, b, w = int(data[p]), int(data[p + 1]), int(data[p + 2])
        p += 3
        adj[a].append((b, w))
        adj[b].append((a, w))
    INF = float("inf")
    layers = k + 1
    dist = [INF] * ((n + 1) * layers)  # state = node * layers + coupons used
    dist[1 * layers] = 0
    heap = [(0, 1 * layers)]
    while heap:
        d, state = heapq.heappop(heap)
        if d > dist[state]:
            continue
        node, used = divmod(state, layers)
        if node == n:
            print(d)
            return
        for nxt, w in adj[node]:
            s = nxt * layers + used
            nd = d + w
            if nd < dist[s]:
                dist[s] = nd
                heapq.heappush(heap, (nd, s))
            if used < k:
                s += 1
                nd = d + w // 2
                if nd < dist[s]:
                    dist[s] = nd
                    heapq.heappush(heap, (nd, s))
    print(-1)


main()
