import re
import sys
import math
import time
import itertools

# ------------------ Safe math & solver ------------------

def is_real_number(x):
    return (x is not None) and (not isinstance(x, complex)) and isinstance(x, (int, float))

def safe_div(a, b):
    try:
        if b == 0:
            return None
        r = a / b
        return r if is_real_number(r) else None
    except Exception:
        return None

def safe_pow(a, b):
    try:
        if abs(a) > 100 or abs(b) > 20:
            return None
        r = a ** b
        return r if is_real_number(r) else None
    except Exception:
        return None

def safe_fact(a):
    if isinstance(a, int) and 0 <= a <= 9:
        return math.factorial(a)
    return None

def safe_sqrt(a):
    if a is None or a < 0:
        return None
    try:
        r = math.sqrt(a)
        return r if is_real_number(r) else None
    except Exception:
        return None

def nested_sqrt(a):
    r1 = safe_sqrt(a)
    if r1 is None:
        return None
    return safe_sqrt(r1)

def unary_forms(x):
    """Return list of (value, expr_str) unary variants for a raw input number."""
    out = []
    out.append((float(x), str(x)))
    r = safe_sqrt(x)
    if r is not None:
        out.append((r, f"sqrt({x})"))
    r2 = nested_sqrt(x)
    if r2 is not None:
        out.append((r2, f"sqrt(sqrt({x}))"))
    f = safe_fact(x)
    if f is not None:
        out.append((float(f), f"({x}!)"))
    return out

def binary_ops(a_val, a_exp, b_val, b_exp):
    """Return list of (value, expr) produced by binary ops between two values."""
    out = []
    try:
        candidates = [
            (a_val + b_val, f"({a_exp}+{b_exp})"),
            (a_val - b_val, f"({a_exp}-{b_exp})"),
            (b_val - a_val, f"({b_exp}-{a_exp})"),
            (a_val * b_val, f"({a_exp}*{b_exp})"),
        ]
        for v, e in candidates:
            if is_real_number(v):
                out.append((v, e))

        d1 = safe_div(a_val, b_val)
        if d1 is not None:
            out.append((d1, f"({a_exp}/{b_exp})"))
        d2 = safe_div(b_val, a_val)
        if d2 is not None:
            out.append((d2, f"({b_exp}/{a_exp})"))

        p1 = safe_pow(a_val, b_val)
        if p1 is not None:
            out.append((p1, f"({a_exp}**{b_exp})"))
        p2 = safe_pow(b_val, a_val)
        if p2 is not None:
            out.append((p2, f"({b_exp}**{a_exp})"))
    except Exception:
        pass
    return out

def sigma3_ops(a_val, a_exp, b_val, b_exp, c_val, c_exp):
    """
    Sigma patterns: sum_{i=start..end} body(i)
    Bodies: i+c, i*c, i*i+c, i*(i+c)
    """
    out = []
    if not (is_real_number(a_val) and is_real_number(b_val) and is_real_number(c_val)):
        return out
    try:
        a_int = int(round(a_val))
        b_int = int(round(b_val))
    except Exception:
        return out
    if a_int < 1 or b_int < 1:
        return out
    start = min(a_int, b_int)
    end   = max(a_int, b_int)
    if end - start > 20 or end > 40:
        return out

    patterns = [
        (lambda i: i + c_val, f"(i+{c_exp})"),
        (lambda i: i * c_val, f"(i*{c_exp})"),
        (lambda i: i*i + c_val, f"(i*i+{c_exp})"),
        (lambda i: i*(i + c_val), f"(i*(i+{c_exp}))"),
    ]
    for func, form in patterns:
        total = 0.0
        valid = True
        for i in range(start, end + 1):
            try:
                v = func(i)
            except Exception:
                valid = False
                break
            if v is None or not is_real_number(v):
                valid = False
                break
            total += v
        if valid:
            expr = f"Σ(i={a_exp}..{b_exp}){form}"
            out.append((float(total), expr))
    return out

def solve_numbers(numbers, target, timeout_seconds=6.0):
    """
    Brute-force solver with unary expansions, pairwise binary combines,
    and sigma-3 reductions.

    Returns (best_value, best_expr, diff) or (None, None, None).
    """
    start_time = time.time()
    start_unaries = [unary_forms(n) for n in numbers]
    best = [9999, None, None]  # [diff, val, expr]
    visited = set()

    def simplify_state(exprs):
        vals = tuple(sorted(round(v, 8) for v, _ in exprs))
        exps = tuple(sorted(e for _, e in exprs))
        return (vals, exps)

    def recurse(expr_list):
        if time.time() - start_time > timeout_seconds:
            return
        state = simplify_state(expr_list)
        if state in visited:
            return
        visited.add(state)

        if len(expr_list) == 1:
            v, e = expr_list[0]
            if not is_real_number(v):
                return
            if abs(v - round(v)) < 1e-9:
                iv = int(round(v))
                if iv > 0:
                    diff = abs(iv - target)
                    if diff < best[0] and diff <= 5:
                        best[0] = diff
                        best[1] = iv
                        best[2] = e
            return

        n = len(expr_list)

        for i in range(n):
            for j in range(i + 1, n):
                a_val, a_exp = expr_list[i]
                b_val, b_exp = expr_list[j]
                for new_val, new_exp in binary_ops(a_val, a_exp, b_val, b_exp):
                    if not is_real_number(new_val):
                        continue
                    new_list = [expr_list[k] for k in range(n) if k not in (i, j)]
                    new_list.append((new_val, new_exp))
                    recurse(new_list)
                    if best[0] == 0 or (time.time() - start_time) > timeout_seconds:
                        return

        if n >= 3:
            for i in range(n):
                for j in range(n):
                    if j == i:
                        continue
                    for k in range(n):
                        if k == i or k == j:
                            continue
                        a_val, a_exp = expr_list[i]
                        b_val, b_exp = expr_list[j]
                        c_val, c_exp = expr_list[k]
                        for new_val, new_exp in sigma3_ops(a_val, a_exp, b_val, b_exp, c_val, c_exp):
                            if not is_real_number(new_val):
                                continue
                            new_list = [expr_list[m] for m in range(n) if m not in (i, j, k)]
                            new_list.append((new_val, new_exp))
                            recurse(new_list)
                            if best[0] == 0 or (time.time() - start_time) > timeout_seconds:
                                return

    for combo in itertools.product(*start_unaries):
        if time.time() - start_time > timeout_seconds:
            break
        exprs = list(combo)
        if any(not is_real_number(v) for v, _ in exprs):
            continue
        recurse(exprs)
        if best[0] == 0:
            break

    if best[1] is None:
        return None, None, None
    return best[1], best[2], best[0]

# ------------------ CLI entry point ------------------

def prompt_and_solve():
    print("\n  Enter numbers then target, all space-separated (e.g. 4 9 1 8 97)")
    print("  Or type 'q' to quit.\n")

    while True:
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if raw.lower() in ("q", "quit", "exit"):
            print("Bye!")
            break
        if not raw:
            continue

        tokens = re.findall(r"-?\d+", raw)
        if len(tokens) < 2:
            print("  Need at least one input number and a target.\n")
            continue

        numbers = [int(t) for t in tokens[:-1]]
        target  = int(tokens[-1])

        print(f"  Numbers: {numbers}  →  Target: {target}")
        val, expr, diff = solve_numbers(numbers, target)

        if val is None:
            print("  No solution found within ±5 or time limit.\n")
        else:
            tag = "exact" if diff == 0 else f"off by {diff}"
            print(f"  Result : {val}  ({tag})")
            print(f"  Expr   : {expr}\n")

if __name__ == "__main__":
    print("=" * 48)
    print("         FastMath Solver")
    print("=" * 48)
    prompt_and_solve()
