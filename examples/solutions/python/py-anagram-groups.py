import sys


def main():
    data = sys.stdin.read().split()
    n = int(data[0])
    groups = {}
    for word in data[1 : 1 + n]:
        groups.setdefault("".join(sorted(word)), set()).add(word)
    lines = sorted(sorted(g) for g in groups.values())
    print("\n".join(" ".join(g) for g in lines))


main()
