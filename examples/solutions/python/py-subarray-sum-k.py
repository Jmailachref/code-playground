import sys


def main():
    data = sys.stdin.buffer.read().split()
    n, k = int(data[0]), int(data[1])
    seen = {0: 1}
    total = 0
    count = 0
    for i in range(2, 2 + n):
        total += int(data[i])
        count += seen.get(total - k, 0)
        seen[total] = seen.get(total, 0) + 1
    print(count)


main()
