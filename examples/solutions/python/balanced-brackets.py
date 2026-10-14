import sys

PAIRS = {")": "(", "]": "[", "}": "{"}


def balanced(text):
    stack = []
    for ch in text:
        if ch in "([{":
            stack.append(ch)
        elif ch in PAIRS and (not stack or stack.pop() != PAIRS[ch]):
            return False
    return not stack


lines = sys.stdin.read().split("\n")
t = int(lines[0])
print("\n".join("YES" if balanced(line.strip()) else "NO" for line in lines[1 : 1 + t]))
