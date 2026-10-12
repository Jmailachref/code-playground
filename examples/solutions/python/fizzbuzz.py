n = int(input())
lines = []
for i in range(1, n + 1):
    lines.append("FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i))
print("\n".join(lines))
