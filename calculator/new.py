import itertools
import math

# ---------------- Safety helpers ----------------

def is_real_number(x):
    return not isinstance(x, complex)

def safe_div(a, b):
    if b == 0:
        return None
    r = a / b
    return r if is_real_number(r) else None

def safe_pow(a, b):
    try:
        if abs(a) > 20 or abs(b) > 10:
            return None
        r = a ** b
        return r if is_real_number(r) else None
    except:
        return None

def safe_fact(a):
    if isinstance(a, int) and 0 <= a <= 10:
        return math.factorial(a)
    return None

def safe_sqrt(a):
    if a < 0:
        return None
    r = math.sqrt(a)
    return r if is_real_number(r) else None

def nested_sqrt(a):
    r1 = safe_sqrt(a)
    if r1 is None:
        return None
    r2 = safe_sqrt(r1)
    return r2

# ---------------- Sigma (two-bound) ----------------

def sigma_range(start, end, body):
    if not (isinstance(start, int) and isinstance(end, int)):
        return None
    if start <= 0 or end <= 0 or end < start:
        return None

    total = 0
    for i in range(start, end + 1):
        v = body(i)
        if v is None or not is_real_number(v):
            return None
        total += v
    return total

def sigma_ops(a_val, a_exp, b_val, b_exp):
    results = []

    # Only allow sigma(i=a..b)(i)    — pure summation
    # This uses NO extra numbers and doesn’t duplicate anything.
    if (isinstance(a_val, int) and 1 <= a_val <= 10 and
        isinstance(b_val, int) and 1 <= b_val <= 10):

        r = sigma_range(a_val, b_val, lambda i: i)
        if r is not None:
            results.append((r, f"Σ(i={a_exp}..{b_exp})(i)"))

    return results


# ---------------- Unary ops ----------------

def unary_forms(x):
    out = [(x, f"{x}")]
    r = safe_sqrt(x)
    if r is not None: out.append((r, f"sqrt({x})"))
    r2 = nested_sqrt(x)
    if r2 is not None: out.append((r2, f"sqrt(sqrt({x}))"))
    f = safe_fact(x)
    if f is not None: out.append((f, f"({x}!)"))
    return out

# ---------------- Binary ops ----------------

def binary_ops(a_val, a_exp, b_val, b_exp):
    ops = []

    base = [
        (a_val + b_val, f"({a_exp}+{b_exp})"),
        (a_val - b_val, f"({a_exp}-{b_exp})"),
        (b_val - a_val, f"({b_exp}-{a_exp})"),
        (a_val * b_val, f"({a_exp}*{b_exp})"),
    ]

    for val, exp in base:
        if is_real_number(val):
            ops.append((val, exp))

    d = safe_div(a_val, b_val)
    if d is not None:
        ops.append((d, f"({a_exp}/{b_exp})"))

    d = safe_div(b_val, a_val)
    if d is not None:
        ops.append((d, f"({b_exp}/{a_exp})"))

    p = safe_pow(a_val, b_val)
    if p is not None:
        ops.append((p, f"({a_exp}**{b_exp})"))

    p = safe_pow(b_val, a_val)
    if p is not None:
        ops.append((p, f"({b_exp}**{a_exp})"))

    return ops

# ---------------- Recursive solver ----------------

def recurse(exprs, target, best):
    # exprs is a list of (value, expression_string)
    if len(exprs) == 1:
        val, exp = exprs[0]
        if abs(val - round(val)) < 1e-9 and val > 0:
            val = int(round(val))
            diff = abs(val - target)
            if diff < best[0]:
                best[0], best[1], best[2] = diff, val, exp
        return

    n = len(exprs)

    # pick every unordered pair (i, j)
    for i in range(n):
        for j in range(i+1, n):
            a_val, a_exp = exprs[i]
            b_val, b_exp = exprs[j]

            combos = []
            combos += binary_ops(a_val, a_exp, b_val, b_exp)
            combos += sigma_ops(a_val, a_exp, b_val, b_exp)

            for v, e in combos:
                if v is None or not is_real_number(v):
                    continue

                new_list = exprs[:i] + exprs[i+1:j] + exprs[j+1:] + [(v, e)]
                recurse(new_list, target, best)

# ---------------- Public interface ----------------

def solve(numbers, target):
    # expand unary possibilities
    start_exprs = []
    for n in numbers:
        start_exprs.append(unary_forms(n))

    # choose 1 unary form per number
    all_choices = itertools.product(*start_exprs)

    best = [999, None, None]  # diff, value, expr

    for choice in all_choices:
        recurse(list(choice), target, best)

        # stop on exact match
        if best[0] == 0:
            break

    return best[1], best[2]


if __name__ == "__main__":
    while True:
        # Ask user to input numbers separated by spaces
        nums = list(map(int, input("Enter numbers separated by spaces: ").split()))

        # Ask user to input the target number
        target = int(input("Enter the target number: "))

        # Print to check
        print("Numbers:", nums)
        print("Target:", target)
        
        val, expr = solve(nums, target)
        print()
        print("\033[91m" + f"Result: {val}" + "\033[0m")
        print("\033[91m" + f"Expression: {expr}" + "\033[0m")
        print("----------------------")
        print()