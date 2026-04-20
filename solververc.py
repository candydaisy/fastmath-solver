#!/usr/bin/env python3
"""
fastmath_auto_full.py

Full GUI + reliable region selector + OCR + auto-detect + solver (auto-run every 5s).
Requirements:
    - Python 3.8+
    - pip install pillow pytesseract
    - Tesseract OCR installed on your system (set TESSERACT_CMD if necessary)
Optional:
    - pip install pyscreenshot   # fallback for Linux screen capture
"""

import re
import sys
import math
import time
import threading
import itertools
import traceback
from collections import deque
from PIL import Image, ImageTk, ImageGrab, ImageOps
import tkinter as tk
from tkinter import ttk, messagebox
import pytesseract

# Optional fallback for Linux screen capture
try:
    import pyscreenshot as pysc
except Exception:
    pysc = None

# If Tesseract is not on PATH, set full path here (optional)
# Example Windows:
# TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

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
        # limit growth to avoid huge/complex numbers
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
    Sigma patterns sum_{i=start..end} body(i)
    Allowed bodies (polynomial-like): i + c, i * c, i*i + c, i*(i + c)
    a_val and b_val must be positive (>=1) ints with moderate range.
    c_val can be any real number.
    """
    out = []

    # Must be real numbers
    if not (is_real_number(a_val) and is_real_number(b_val) and is_real_number(c_val)):
        return out

    # Convert floats that are essentially integers
    try:
        a_int = int(round(a_val))
        b_int = int(round(b_val))
    except Exception:
        return out

    # Only allow positive start/end for sigma
    if a_int < 1 or b_int < 1:
        return out

    start = min(a_int, b_int)
    end = max(a_int, b_int)

    # Prevent huge sums
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
    Brute-force-ish solver with:
    - unary expansions of inputs
    - pairwise binary combines + sigma-3 reductions
    - returns (best_value, best_expr, diff) or (None, None, None)
    """
    start_time = time.time()
    start_unaries = [unary_forms(n) for n in numbers]
    best = [9999, None, None]  # diff, val, expr
    visited = set()

    def simplify_state(exprs):
        # exprs: list of (val, expr)
        vals = tuple(sorted(round(v, 8) for v, _ in exprs))
        exps = tuple(sorted(e for _, e in exprs))
        return (vals, exps)

    def recurse(expr_list):
        # timeout guard
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
        # combine binary pairs
        for i in range(n):
            for j in range(i+1, n):
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

        # try sigma3 reductions if possible
        if n >= 3:
            idxs = range(n)
            for i in idxs:
                for j in idxs:
                    if j == i:
                        continue
                    for k in idxs:
                        if k == i or k == j:
                            continue
                        a_val, a_exp = expr_list[i]
                        b_val, b_exp = expr_list[j]
                        c_val, c_exp = expr_list[k]
                        for new_val, new_exp in sigma3_ops(a_val, a_exp, b_val, b_exp, c_val, c_exp):
                            if not is_real_number(new_val):
                                continue
                            new_list = [expr_list[m] for m in idxs if m not in (i, j, k)]
                            new_list.append((new_val, new_exp))
                            recurse(new_list)
                            if best[0] == 0 or (time.time() - start_time) > timeout_seconds:
                                return

    # iterate unary choices
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

# ------------------ OCR helpers ------------------

def enhance_for_ocr(img: Image.Image) -> Image.Image:
    """Convert to grayscale, autocontrast, resize a bit, threshold to reduce noise."""
    g = img.convert("L")
    w, h = g.size
    if w < 300:
        factor = max(2, 300 // max(1, w))
        g = g.resize((w * factor, h * factor), Image.Resampling.LANCZOS)
    g = ImageOps.autocontrast(g)
    # Threshold to B/W then convert back to L for tesseract reliability
    bw = g.point(lambda p: 0 if p < 160 else 255, '1')
    return bw.convert("L")

def grab_screen_region(bbox):
    """Grab a screen region. Use PIL.ImageGrab or fallback to pyscreenshot."""
    try:
        img = ImageGrab.grab(bbox)
        return img
    except Exception:
        if pysc:
            try:
                img = pysc.grab(bbox=bbox)
                return img
            except Exception:
                raise
        else:
            raise

def ocr_extract_numbers_from_image(img: Image.Image):
    """Return list of ints found in image (in reading order) using digit-prioritized tesseract."""
    img2 = enhance_for_ocr(img)
    config = "--oem 3 --psm 6 outputbase digits"
    txt = pytesseract.image_to_string(img2, config=config)
    nums = re.findall(r"-?\d+", txt)
    return [int(x) for x in nums]

def split_numbers_and_target(nums):
    """
    Heuristic split:
      - if exactly 5 numbers: first 4 inputs, last target
      - if 4: assume these are inputs, target left blank
      - if >5: take first 4 as inputs, largest as target
      - if 3: use largest as target if it's much larger else return inputs only
    """
    if not nums:
        return [], None
    if len(nums) == 4:
        return nums, None
    if len(nums) == 5:
        return nums[:-1], nums[-1]
    if len(nums) > 5:
        return nums[:4], max(nums, key=abs)
    if len(nums) == 3:
        largest = max(nums, key=abs)
        others = [x for x in nums if x != largest]
        if len(others) == 2:
            return others, largest
        return nums, None
    if len(nums) == 2:
        return [nums[0]], nums[1]
    return nums, None

# ------------------ Reliable RegionSelector ------------------

class RegionSelector(tk.Toplevel):
    """
    Reliable region selection overlay:
    - fullscreen semi-transparent overlay
    - draws red rectangle while dragging
    - returns bbox in screen coordinates (left, top, right, bottom)
    """

    def __init__(self, master, title="Select region (Esc to cancel)"):
        super().__init__(master)
        self.master = master
        self.title(title)

        # Make fullscreen and topmost
        try:
            self.attributes("-fullscreen", True)
        except Exception:
            # fallback to manual geometry
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        # semi-transparent overlay so user can see screen
        try:
            self.attributes("-alpha", 0.28)
        except Exception:
            pass

        self.canvas = tk.Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.bbox = None

        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.cancel())

    def cancel(self):
        self.bbox = None
        self.destroy()

    def on_button_press(self, event):
        # store screen pointer coords
        self.start_x = self.winfo_pointerx()
        self.start_y = self.winfo_pointery()
        # draw rectangle in canvas; coords are screen coords but canvas covers full screen
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x + 1, self.start_y + 1,
                                                 outline="red", width=3)

    def on_move(self, event):
        if not self.rect:
            return
        cur_x = self.winfo_pointerx()
        cur_y = self.winfo_pointery()
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        end_x = self.winfo_pointerx()
        end_y = self.winfo_pointery()
        self.bbox = (min(self.start_x, end_x),
                     min(self.start_y, end_y),
                     max(self.start_x, end_x),
                     max(self.start_y, end_y))
        self.destroy()

# ------------------ Main GUI App ------------------

class FastMathAutoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FastMath Auto Detective & Solver")
        self.geometry("980x720")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # state
        self.numbers_region_bbox = None
        self.target_region_bbox = None
        self.last_capture = None
        self.auto_interval_seconds = 5.0
        self.solver_timeout = 6.0
        self.auto_running = False
        self._auto_thread = None
        self._stop_event = threading.Event()
        self._solver_thread = None

        self.log_lines = deque(maxlen=300)

        self.build_ui()

        # start auto-cycle when auto_enabled toggled by user. We don't auto-start by default.
        # But we add an "Start Auto" button in UI.
        # Note: user must select regions first.

    def build_ui(self):
        pad = 8
        frm = ttk.Frame(self, padding=pad)
        frm.pack(fill="both", expand=True)

        top = ttk.Frame(frm)
        top.pack(fill="x", pady=(0,pad))

        ttk.Label(top, text="Numbers (space-separated):").grid(column=0, row=0, sticky="w")
        self.nums_var = tk.StringVar(value="4 9 1 8")
        ttk.Entry(top, width=36, textvariable=self.nums_var).grid(column=1, row=0, sticky="w", padx=(6,12))
        ttk.Button(top, text="Select Region (auto inputs+target)", command=self.select_region_auto).grid(column=2, row=0, padx=6)
        ttk.Button(top, text="Select Numbers Region", command=self.select_numbers_region).grid(column=3, row=0, padx=6)

        ttk.Label(top, text="Target:").grid(column=0, row=1, sticky="w", pady=(6,0))
        self.target_var = tk.StringVar(value="97")
        ttk.Entry(top, width=20, textvariable=self.target_var).grid(column=1, row=1, sticky="w", padx=(6,12), pady=(6,0))
        ttk.Button(top, text="Select Target Region", command=self.select_target_region).grid(column=3, row=1, padx=6, pady=(6,0))
        ttk.Button(top, text="Detect target in last region", command=self.detect_target_in_last).grid(column=2, row=1, padx=6, pady=(6,0))

        mid = ttk.Frame(frm)
        mid.pack(fill="both", expand=True, pady=(0,pad))

        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Parsed OCR results:").pack(anchor="w")
        self.ocr_text = tk.Text(left, width=60, height=12)
        self.ocr_text.pack(fill="both", expand=False)

        ctrl = ttk.Frame(left)
        ctrl.pack(fill="x", pady=(6,0))
        ttk.Label(ctrl, text="Solver timeout (s):").grid(column=0, row=0, sticky="w")
        self.timeout_var = tk.DoubleVar(value=self.solver_timeout)
        ttk.Entry(ctrl, width=6, textvariable=self.timeout_var).grid(column=1, row=0, padx=6)
        ttk.Label(ctrl, text="Auto-interval (s):").grid(column=2, row=0, sticky="w", padx=(10,0))
        self.interval_var = tk.DoubleVar(value=self.auto_interval_seconds)
        ttk.Entry(ctrl, width=6, textvariable=self.interval_var).grid(column=3, row=0, padx=6)
        self.auto_button = ttk.Button(ctrl, text="Start Auto (5s)", command=self.toggle_auto)
        self.auto_button.grid(column=4, row=0, padx=(12,0))

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(6,0))
        ttk.Button(btns, text="Run solver now", command=self.run_solver_thread).pack(side="left")
        ttk.Button(btns, text="Clear OCR", command=lambda: self.ocr_text.delete("1.0", "end")).pack(side="left", padx=6)

        right = ttk.Frame(mid, width=420)
        right.pack(side="left", fill="both", expand=False, padx=(12,0))
        ttk.Label(right, text="Result:").pack(anchor="w")
        self.result_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.result_var, font=("Segoe UI", 12)).pack(anchor="w", pady=(0,6))
        ttk.Label(right, text="Expression:").pack(anchor="w")
        self.expr_text = tk.Text(right, width=58, height=8)
        self.expr_text.pack(fill="both", expand=False)

        btm = ttk.Frame(frm)
        btm.pack(fill="both", expand=True)
        ttk.Label(btm, text="Log:").pack(anchor="w")
        self.log_text = tk.Text(btm, height=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    # ---------- Logging ----------
    def log(self, *parts):
        ts = time.strftime("%H:%M:%S")
        msg = " ".join(str(p) for p in parts)
        line = f"[{ts}] {msg}"
        self.log_lines.append(line)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", "\n".join(self.log_lines))
        self.log_text.configure(state="disabled")

    # ---------- region selection flows ----------
    def select_region_auto(self):
        """Select one region containing both digits and target; heuristic split."""
        self.log("Please select a region containing the inputs and target.")
        sel = RegionSelector(self, title="Select region containing inputs and target (Esc to cancel)")
        self.wait_window(sel)
        bbox = getattr(sel, "bbox", None)
        if not bbox:
            self.log("Selection cancelled.")
            return
        try:
            img = grab_screen_region(bbox)
            self.last_capture = img
        except Exception as e:
            self.log("Capture failed:", e)
            messagebox.showerror("Capture error", f"Screen capture failed: {e}\nTry installing pyscreenshot or scrot on Linux.")
            return

        # OCR in background
        def job():
            try:
                nums = ocr_extract_numbers_from_image(img)
                self.ocr_text.delete("1.0", "end")
                if nums:
                    self.ocr_text.insert("1.0", "Raw numbers found: " + ", ".join(map(str, nums)) + "\n\n")
                else:
                    self.ocr_text.insert("1.0", "No numbers found by OCR.\n\n")
                full = pytesseract.image_to_string(enhance_for_ocr(img))
                self.ocr_text.insert("end", "Full OCR text:\n" + full + "\n")

                inputs, target = split_numbers_and_target(nums)
                # convert inputs to space-separated individual digits
                digits = []
                for n in inputs:
                    for ch in str(abs(n)):
                        if ch.isdigit():
                            digits.append(ch)
                if digits:
                    self.nums_var.set(" ".join(digits))
                if target is not None:
                    self.target_var.set(str(target))
                # store region as both numbers & target fallback
                self.numbers_region_bbox = bbox
                self.target_region_bbox = bbox
                self.log("Auto-detect completed. Regions saved; you can edit values.")
            except Exception as e:
                self.log("OCR error:", e)
                traceback.print_exc()

        threading.Thread(target=job, daemon=True).start()

    def select_numbers_region(self):
        sel = RegionSelector(self, title="Select region for INPUT NUMBERS (Esc to cancel)")
        self.wait_window(sel)
        bbox = getattr(sel, "bbox", None)
        if not bbox:
            self.log("Numbers selection cancelled.")
            return
        try:
            img = grab_screen_region(bbox)
            self.last_capture = img
        except Exception as e:
            self.log("Capture failed:", e)
            messagebox.showerror("Capture error", str(e))
            return

        def job():
            try:
                nums = ocr_extract_numbers_from_image(img)
                self.ocr_text.delete("1.0", "end")
                if not nums:
                    self.ocr_text.insert("1.0", "No digits found in region.\n")
                    self.log("No digits found for numbers region.")
                else:
                    self.ocr_text.insert("1.0", "Numbers region OCR: " + ", ".join(map(str, nums)) + "\n")
                    # space-separate digits (split each multi-digit into digits)
                    digits = []
                    for n in nums:
                        for ch in str(abs(n)):
                            if ch.isdigit():
                                digits.append(ch)
                    if digits:
                        self.nums_var.set(" ".join(digits))
                self.numbers_region_bbox = bbox
                self.log("Numbers region saved.")
            except Exception as e:
                self.log("OCR error:", e)

        threading.Thread(target=job, daemon=True).start()

    def select_target_region(self):
        sel = RegionSelector(self, title="Select region for TARGET (Esc to cancel)")
        self.wait_window(sel)
        bbox = getattr(sel, "bbox", None)
        if not bbox:
            self.log("Target selection cancelled.")
            return
        try:
            img = grab_screen_region(bbox)
            self.last_capture = img
        except Exception as e:
            self.log("Capture failed:", e)
            messagebox.showerror("Capture error", str(e))
            return

        def job():
            try:
                nums = ocr_extract_numbers_from_image(img)
                self.ocr_text.delete("1.0", "end")
                if nums:
                    self.ocr_text.insert("1.0", "Target OCR: " + ", ".join(map(str, nums)) + "\n")
                    self.target_var.set(str(nums[-1]))
                else:
                    self.ocr_text.insert("1.0", "No digits found in target region.\n")
                self.target_region_bbox = bbox
                self.log("Target region saved.")
            except Exception as e:
                self.log("OCR error:", e)

        threading.Thread(target=job, daemon=True).start()

    def detect_target_in_last(self):
        if self.last_capture is None:
            messagebox.showinfo("Info", "No previous capture found. Use a region selection first.")
            return
        try:
            nums = ocr_extract_numbers_from_image(self.last_capture)
            if not nums:
                messagebox.showinfo("No numbers", "OCR didn't find numbers in the last region.")
                return
            cand = max(nums, key=abs)
            self.target_var.set(str(cand))
            self.log("Target heuristic set to", cand)
        except Exception as e:
            self.log("Detect target failed:", e)

    # ---------- solver orchestration ----------
    def run_solver_thread(self):
        if self._solver_thread and self._solver_thread.is_alive():
            self.log("Solver is already running.")
            return
        t = threading.Thread(target=self._run_solver, daemon=True)
        self._solver_thread = t
        t.start()

    def _run_solver(self):
        self.result_var.set("Running...")
        self.expr_text.delete("1.0", "end")
        try:
            # parse numbers as digits separated by spaces
            raw = self.nums_var.get().strip()
            # Accept digits separated by spaces, or multi-digit numbers as fallback
            digits = re.findall(r"-?\d+", raw)
            if not digits:
                messagebox.showerror("Input error", "No input numbers found.")
                self.result_var.set("Input error")
                return
            # convert each token to int (if tokens are single-digit it's fine)
            numbers = [int(x) for x in digits]
            # target
            tmatch = re.search(r"-?\d+", self.target_var.get() or "")
            if not tmatch:
                messagebox.showerror("Target error", "Target not parseable.")
                self.result_var.set("Target parse error")
                return
            target = int(tmatch.group(0))
        except Exception as e:
            self.log("Input parse error:", e)
            self.result_var.set("Input parse error")
            return

        timeout = float(self.timeout_var.get())
        self.log("Solver started:", numbers, "target", target, "timeout", timeout)
        try:
            val, expr, diff = solve_numbers(numbers, target, timeout_seconds=timeout)
            if val is None:
                self.result_var.set("No solution found within tolerance/time")
                self.expr_text.insert("1.0", "No expression found (exact or within ±5) in time limit.\n")
                self.log("Solver: no solution")
            else:
                self.result_var.set(f"{val} (diff {diff})")
                self.expr_text.insert("1.0", expr)
                self.log("Solver result:", val, "expr:", expr, "diff:", diff)
        except Exception as e:
            self.log("Solver error:", e)
            traceback.print_exc()
            self.result_var.set("Solver error")
            self.expr_text.insert("1.0", str(e))

    # ---------- auto-cycle (re-detect + solve) ----------
    def toggle_auto(self):
        if not self.auto_running:
            # start auto
            try:
                interval = float(self.interval_var.get())
            except Exception:
                interval = 5.0
                self.interval_var.set(interval)
            self.auto_interval_seconds = interval
            self._stop_event.clear()
            self._auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
            self._auto_thread.start()
            self.auto_running = True
            self.auto_button.config(text=f"Stop Auto ({interval:.0f}s)")
            self.log("Auto-cycle started (interval", interval, "s).")
        else:
            # stop auto
            self._stop_event.set()
            self.auto_running = False
            self.auto_button.config(text=f"Start Auto ({self.interval_var.get()}s)")
            self.log("Auto-cycle stopped.")

    def _auto_loop(self):
        interval = float(self.interval_var.get())
        while not self._stop_event.is_set():
            # re-run OCR for numbers region
            try:
                if self.numbers_region_bbox:
                    try:
                        img = grab_screen_region(self.numbers_region_bbox)
                        self.last_capture = img
                        nums = ocr_extract_numbers_from_image(img)
                        # break multi-digit into digits and set
                        digits = []
                        for n in nums:
                            for ch in str(abs(n)):
                                if ch.isdigit():
                                    digits.append(ch)
                        if digits:
                            # update in main thread
                            self.after(0, lambda d=digits: self.nums_var.set(" ".join(d)))
                            self.log("Auto OCR updated numbers:", " ".join(digits))
                    except Exception as e:
                        self.log("Auto OCR numbers failed:", e)
                # re-run OCR for target region
                if self.target_region_bbox:
                    try:
                        img2 = grab_screen_region(self.target_region_bbox)
                        self.last_capture = img2
                        nums2 = ocr_extract_numbers_from_image(img2)
                        if nums2:
                            tval = nums2[-1]
                            self.after(0, lambda tv=tval: self.target_var.set(str(tv)))
                            self.log("Auto OCR updated target:", tval)
                    except Exception as e:
                        self.log("Auto OCR target failed:", e)
            except Exception as e:
                self.log("Auto-cycle capture error:", e)
            # run solver
            self.after(0, self.run_solver_thread)
            # wait interval (check stop event more frequently)
            slept = 0.0
            while slept < interval and not self._stop_event.is_set():
                time.sleep(0.2)
                slept += 0.2

    def on_close(self):
        self._stop_event.set()
        try:
            self.destroy()
        except Exception:
            pass

def main():
    app = FastMathAutoApp()
    app.mainloop()

if __name__ == "__main__":
    main()
