"""
solver_gui_autodetect.py

GUI + screen-region auto-detect (OCR) + solver (no-reuse sigma-3, polynomial sigma bodies)
Requirements: Python 3.8+, Pillow, pytesseract, Tesseract OCR installed.
pip install pillow pytesseract
"""

import re
import sys
import itertools
import math
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageGrab
import pytesseract
import threading
import time
import os

# If Tesseract is not on PATH, set full path here:
# Example Windows: r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_CMD = None
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# ---------------- Solver code (upgraded + safe + sigma-3) ----------------

def is_real_number(x):
    return not isinstance(x, complex)

def safe_div(a, b):
    if b == 0:
        return None
    r = a / b
    return r if is_real_number(r) else None

def safe_pow(a, b):
    try:
        if abs(a) > 15 or abs(b) > 8:
            return None
        r = a ** b
        return r if is_real_number(r) else None
    except:
        return None

def safe_fact(a):
    if isinstance(a, int) and 0 <= a <= 8:
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

def unary_forms(x):
    out = [(x, f"{x}")]
    r = safe_sqrt(x)
    if r is not None:
        out.append((r, f"sqrt({x})"))
    r2 = nested_sqrt(x)
    if r2 is not None:
        out.append((r2, f"sqrt(sqrt({x}))"))
    f = safe_fact(x)
    if f is not None:
        out.append((f, f"({x}!)"))
    return out

def binary_ops(a_val, a_exp, b_val, b_exp):
    results = []
    base = [
        (a_val + b_val, f"({a_exp}+{b_exp})"),
        (a_val - b_val, f"({a_exp}-{b_exp})"),
        (b_val - a_val, f"({b_exp}-{a_exp})"),
        (a_val * b_val, f"({a_exp}*{b_exp})")
    ]
    for v, e in base:
        if is_real_number(v):
            results.append((v, e))

    d = safe_div(a_val, b_val)
    if d is not None:
        results.append((d, f"({a_exp}/{b_exp})"))
    d = safe_div(b_val, a_val)
    if d is not None:
        results.append((d, f"({b_exp}/{a_exp})"))

    p = safe_pow(a_val, b_val)
    if p is not None:
        results.append((p, f"({a_exp}**{b_exp})"))
    p = safe_pow(b_val, a_val)
    if p is not None:
        results.append((p, f"({b_exp}**{a_exp})"))
    return results

def sigma3_ops(a_val, a_exp, b_val, b_exp, c_val, c_exp):
    results = []
    if not (isinstance(a_val, int) and isinstance(b_val, int)):
        return results
    if a_val <= 0 or b_val <= 0:
        return results
    start = min(a_val, b_val)
    end = max(a_val, b_val)
    if end > 12:
        return results
    patterns = [
        (lambda i: i + c_val,     f"(i+{c_exp})"),
        (lambda i: i * c_val,     f"(i*{c_exp})"),
        (lambda i: i*i + c_val,   f"(i*i+{c_exp})"),
        (lambda i: i*(i + c_val), f"(i*(i+{c_exp}))"),
    ]
    for body_func, body_exp in patterns:
        total = 0
        valid = True
        for i in range(start, end+1):
            try:
                v = body_func(i)
            except Exception:
                valid = False
                break
            if v is None or not is_real_number(v):
                valid = False
                break
            total += v
        if valid:
            expr = f"Σ(i={a_exp}..{b_exp}){body_exp}"
            results.append((total, expr))
    return results

# memoization cache
cache = {}
def simplify_state(exprs):
    # sort by rounded value to be order-independent
    return tuple(sorted(round(val, 6) for val, _ in exprs))

def recurse(exprs, target, best):
    state = simplify_state(exprs)
    if state in cache:
        return
    cache[state] = True

    if len(exprs) == 1:
        val, exp = exprs[0]
        if abs(val - round(val)) < 1e-9 and val > 0:
            val = int(round(val))
            diff = abs(val - target)
            if diff < best[0]:
                best[0] = diff
                best[1] = val
                best[2] = exp
        return

    n = len(exprs)

    # binary combines
    for i in range(n):
        for j in range(i+1, n):
            a_val, a_exp = exprs[i]
            b_val, b_exp = exprs[j]
            for v, e in binary_ops(a_val, a_exp, b_val, b_exp):
                if not is_real_number(v):
                    continue
                new_list = [exprs[k] for k in range(n) if k not in (i, j)]
                new_list.append((v, e))
                recurse(new_list, target, best)

    # sigma combines (3 -> 1)
    if n >= 3:
        for i in range(n):
            for j in range(n):
                if j == i:
                    continue
                for k in range(n):
                    if k == i or k == j:
                        continue
                    a_val, a_exp = exprs[i]
                    b_val, b_exp = exprs[j]
                    c_val, c_exp = exprs[k]
                    for v, e in sigma3_ops(a_val, a_exp, b_val, b_exp, c_val, c_exp):
                        if not is_real_number(v):
                            continue
                        new_list = [exprs[m] for m in range(n) if m not in (i, j, k)]
                        new_list.append((v, e))
                        recurse(new_list, target, best)

def solve(numbers, target, timeout_seconds=6):
    # reset cache
    global cache
    cache = {}
    start_exprs = [unary_forms(n) for n in numbers]
    all_choices = itertools.product(*start_exprs)
    best = [999, None, None]
    start_time = time.time()

    for choice in all_choices:
        # timeout guard
        if time.time() - start_time > timeout_seconds:
            break
        recurse(list(choice), target, best)
        if best[0] == 0:
            break
    return best[1], best[2], best[0]

# ---------------- OCR / Auto-detect helpers ----------------

def ocr_extract_numbers_from_image(img):
    gray = img.convert("L")
    gray = gray.resize((gray.width * 2, gray.height * 2))
    gray = gray.point(lambda x: 0 if x < 160 else 255, '1')

    text = pytesseract.image_to_string(gray, config="--oem 3 --psm 6 outputbase digits")
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums]


# ---------------- GUI: region selector ----------------

class RegionSelector(tk.Toplevel):
    """
    Window to select a rectangle region safely.
    Works on Windows without freezing or blocking.
    """
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        # Make this top-level semi-transparent
        # (apply to this Toplevel window itself)
        try:
            self.attributes("-alpha", 0.3)
        except Exception:
            # On some platforms this may not be supported — ignore gracefully
            pass

        self.title("Drag to select region (Esc to cancel)")

        # Make the toplevel fill the screen so we can draw on it
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

        # Full-size canvas for the selection overlay
        self.canvas = tk.Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.start_x_screen = None   # screen coords
        self.start_y_screen = None
        self.rect = None
        self.bbox = None

        # Bind events
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.destroy())

        # Ensure the window is on top so user can select
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

    def _screen_to_canvas(self, x_root, y_root):
        """Convert screen (root) coords to canvas-local coords."""
        cx = x_root - self.winfo_rootx()
        cy = y_root - self.winfo_rooty()
        return cx, cy

    def on_button_press(self, event):
        # store screen coords for ImageGrab later
        self.start_x_screen = event.x_root
        self.start_y_screen = event.y_root

        # convert to canvas coords for drawing
        cx, cy = self._screen_to_canvas(event.x_root, event.y_root)

        # create rectangle in canvas coords
        self.rect = self.canvas.create_rectangle(cx, cy, cx+1, cy+1,
                                                 outline="red", width=2)

    def on_move(self, event):
        if not self.rect:
            return

        # current mouse screen coords
        cur_x_screen = event.x_root
        cur_y_screen = event.y_root

        # convert to canvas coords
        cx1, cy1 = self._screen_to_canvas(self.start_x_screen, self.start_y_screen)
        cx2, cy2 = self._screen_to_canvas(cur_x_screen, cur_y_screen)

        # update rectangle on canvas using canvas coords
        self.canvas.coords(self.rect, cx1, cy1, cx2, cy2)

    def on_release(self, event):
        # final screen coords
        x2_screen = event.x_root
        y2_screen = event.y_root

        # store bbox in screen coordinates (left, top, right, bottom)
        self.bbox = (min(self.start_x_screen, x2_screen),
                     min(self.start_y_screen, y2_screen),
                     max(self.start_x_screen, x2_screen),
                     max(self.start_y_screen, y2_screen))

        # close selector
        self.destroy()



# ---------------- GUI main app ----------------

class SolverApp(tk.Tk):

    def __init__(self):
        super().__init__() 

        self.title("TOTALLY NOT THE FASTMATH CHEAT BTW")
        self.geometry("820x520")

        self.numbers_region_bbox = None
        self.numbers_region_image = None

        self.target_region_bbox = None
        self.target_region_image = None

        self.last_region_image = None
        self.last_region_bbox = None

        self.create_widgets() 


    def create_widgets(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        # Input area
        row = 0
        ttk.Label(frm, text="Numbers (space-separated):").grid(column=0, row=row, sticky="w")
        self.nums_var = tk.StringVar(value="4 9 1 8")
        ttk.Entry(frm, width=40, textvariable=self.nums_var).grid(column=1, row=row, sticky="w")

        ttk.Button(frm, text="Select Numbers Region", command=self.select_numbers_region)\
        .grid(column=2, row=0, padx=4)

        ttk.Button(frm, text="Select Target Region", command=self.select_target_region)\
        .grid(column=2, row=1, padx=4)


        row += 1
        ttk.Label(frm, text="Target:").grid(column=0, row=row, sticky="w")
        self.target_var = tk.StringVar(value="97")
        ttk.Entry(frm, width=20, textvariable=self.target_var).grid(column=1, row=row, sticky="w")
        ttk.Button(frm, text="Detect target in same region", command=self.detect_target_in_last).grid(column=2, row=row, padx=4)

        row += 1
        ttk.Label(frm, text="Parsed OCR results:").grid(column=0, row=row, sticky="nw")
        self.ocr_text = tk.Text(frm, width=60, height=8)
        self.ocr_text.grid(column=1, row=row, columnspan=2, sticky="w")

        row += 1
        ttk.Button(frm, text="Run Solver", command=self.run_solver_thread).grid(column=0, row=row, pady=8)
        ttk.Button(frm, text="Clear OCR", command=lambda: self.ocr_text.delete("1.0", "end")).grid(column=1, row=row, sticky="w")

        row += 1
        ttk.Label(frm, text="Result:").grid(column=0, row=row, sticky="w")
        self.result_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.result_var, font=("Segoe UI", 11)).grid(column=1, row=row, sticky="w")

        row += 1
        ttk.Label(frm, text="Expression:").grid(column=0, row=row, sticky="nw")
        self.expr_text = tk.Text(frm, width=60, height=6)
        self.expr_text.grid(column=1, row=row, columnspan=2, sticky="w")

        # status
        row += 1
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frm, textvariable=self.status_var).grid(column=0, row=row, columnspan=3, sticky="w", pady=(8,0))

        # internal
        self.last_region_image = None
        self.last_region_bbox = None

    def start_region_ocr(self):
        # Ask user to select region
        self.status_var.set("Select region — click and drag (Esc to cancel)")
        self.update()
        sel = RegionSelector(self)
        self.wait_window(sel)
        bbox = getattr(sel, "bbox", None)
        if not bbox:
            self.status_var.set("Region selection cancelled")
            return
        self.last_region_bbox = bbox
        try:
            img = ImageGrab.grab(bbox)
        except Exception:
            messagebox.showerror("Error", "Screen capture failed on this platform. If you're on Linux, install pyscreenshot and restart.")
            self.status_var.set("Capture failed")
            return
        self.last_region_image = img
        self.status_var.set("Running OCR on selected region...")
        self.update()
        # run OCR in background to keep UI responsive
        def ocr_job():
            try:
                nums = ocr_extract_numbers_from_image(img)
            except Exception as e:
                self.status_var.set("OCR error: " + str(e))
                return
            self.ocr_text.delete("1.0", "end")
            self.ocr_text.insert("1.0", "Raw OCR numbers found (in order):\n")
            self.ocr_text.insert("end", ", ".join(str(x) for x in nums) + "\n\n")
            self.ocr_text.insert("end", "Full OCR text:\n")
            fulltext = pytesseract.image_to_string(img)
            self.ocr_text.insert("end", fulltext)
            # If numbers look like first N are the inputs and last is target, prefill
            if len(nums) >= 2:
                # heuristic: if many numbers, assume last or largest is target
                # We'll leave numbers text input populated; user can edit
                self.nums_var.set(" ".join(str(x) for x in nums[:-1]))
                self.target_var.set(str(nums[-1]))
            self.status_var.set("OCR done — edit parsed values if needed")
        threading.Thread(target=ocr_job, daemon=True).start()

    def detect_target_in_last(self):
        if self.last_region_image is None:
            messagebox.showinfo("Info", "First use Auto-detect to select a region.")
            return
        # run OCR and try to guess the target only
        try:
            nums = ocr_extract_numbers_from_image(self.last_region_image)
        except Exception as e:
            messagebox.showerror("OCR error", str(e))
            return
        if not nums:
            messagebox.showinfo("No numbers found", "OCR didn't find numbers in that region.")
            return
        # heuristic: largest or last
        cand = max(nums, key=abs)
        self.target_var.set(str(cand))
        self.status_var.set("Target detected (heuristic). Please verify.")

    def run_solver_thread(self):
        # run solver in separate thread
        t = threading.Thread(target=self.run_solver, daemon=True)
        t.start()

    def run_solver(self):
        self.status_var.set("Running solver...")
        self.result_var.set("")
        self.expr_text.delete("1.0", "end")
        try:
            nums = [int(x) for x in re.findall(r"-?\d+", self.nums_var.get())]
            target_match = re.search(r"-?\d+", self.target_var.get())
            if not target_match:
                messagebox.showerror("Input error", "Couldn't parse target integer.")
                self.status_var.set("Input error")
                return
            target = int(target_match.group(0))
        except Exception as e:
            messagebox.showerror("Input error", str(e))
            self.status_var.set("Input error")
            return

        if len(nums) < 2:
            messagebox.showerror("Need more numbers", "Please provide at least 2 input numbers.")
            self.status_var.set("Need more numbers")
            return

        # call solver with a modest timeout for GUI responsiveness
        val, expr, diff = solve(nums, target, timeout_seconds=8)
        if val is None:
            self.result_var.set("No solution found (within tolerance)")
            self.expr_text.insert("1.0", "No expression found within tolerance or time limit.\n")
        else:
            self.result_var.set(f"{val} (diff {diff})")
            self.expr_text.insert("1.0", expr)
        self.status_var.set("Done")
    
    def select_numbers_region(self):
        self.status_var.set("Select NUMBERS region — click and drag")
        self.update()

        sel = RegionSelector(self)
        self.wait_window(sel)

        if not sel.bbox:
            self.status_var.set("Selection cancelled")
            return

        self.numbers_region_bbox = sel.bbox
        self.numbers_region_image = ImageGrab.grab(sel.bbox)

        nums = ocr_extract_numbers_from_image(self.numbers_region_image)

        self.ocr_text.delete("1.0", "end")
        self.ocr_text.insert("1.0", "Numbers region OCR:\n")
        self.ocr_text.insert("end", ", ".join(str(x) for x in nums))

        if nums:
            self.nums_var.set(" ".join(map(str, nums)))

        self.status_var.set("Numbers region saved")
    
    def select_target_region(self):
        self.status_var.set("Select TARGET region — click and drag")
        self.update()

        sel = RegionSelector(self)
        self.wait_window(sel)

        if not sel.bbox:
            self.status_var.set("Selection cancelled")
            return

        self.target_region_bbox = sel.bbox
        self.target_region_image = ImageGrab.grab(sel.bbox)

        nums = ocr_extract_numbers_from_image(self.target_region_image)

        if nums:
            self.target_var.set(str(nums[0]))

        self.status_var.set("Target region saved")




# ---------------- Run app ----------------

def main():
    app = SolverApp()
    app.mainloop()

if __name__ == "__main__":
    main()