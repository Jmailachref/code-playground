import sys


def main():
    data = sys.stdin.buffer.read().split()
    n, q = int(data[0]), int(data[1])
    size = 1
    while size < n:
        size *= 2
    NEG = -(10**18)
    # Each node keeps total, best prefix, best suffix, best subarray (non-empty).
    tot = [0] * (2 * size)
    pre = [NEG] * (2 * size)
    suf = [NEG] * (2 * size)
    best = [NEG] * (2 * size)

    def set_leaf(i, v):
        tot[i] = pre[i] = suf[i] = best[i] = v

    def pull(i):
        l, r = 2 * i, 2 * i + 1
        tot[i] = tot[l] + tot[r]
        pre[i] = max(pre[l], tot[l] + pre[r])
        suf[i] = max(suf[r], tot[r] + suf[l])
        best[i] = max(best[l], best[r], suf[l] + pre[r])

    for i in range(n):
        set_leaf(size + i, int(data[2 + i]))
    for i in range(size - 1, 0, -1):
        pull(i)

    out = []
    p = 2 + n
    for _ in range(q):
        op, a, b = data[p], int(data[p + 1]), int(data[p + 2])
        p += 3
        if op == b"U":
            i = size + a - 1
            set_leaf(i, b)
            i //= 2
            while i:
                pull(i)
                i //= 2
        else:
            # Combine left pieces in order, right pieces in reverse order.
            lo, hi = a - 1 + size, b + size
            left = None
            right = []
            while lo < hi:
                if lo & 1:
                    node = (tot[lo], pre[lo], suf[lo], best[lo])
                    if left is None:
                        left = node
                    else:
                        lt, lp, ls, lb = left
                        rt, rp, rs, rb = node
                        left = (lt + rt, max(lp, lt + rp), max(rs, rt + ls), max(lb, rb, ls + rp))
                    lo += 1
                if hi & 1:
                    hi -= 1
                    right.append((tot[hi], pre[hi], suf[hi], best[hi]))
                lo //= 2
                hi //= 2
            for node in reversed(right):
                if left is None:
                    left = node
                else:
                    lt, lp, ls, lb = left
                    rt, rp, rs, rb = node
                    left = (lt + rt, max(lp, lt + rp), max(rs, rt + ls), max(lb, rb, ls + rp))
            out.append(left[3])
    sys.stdout.write("\n".join(map(str, out)) + ("\n" if out else ""))


main()
