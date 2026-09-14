# FastMath

A small web front end for the FastMath number solver.

## Files

- `solver.py` — the solver logic (unchanged math from `fastmath_solver.py`, CLI loop removed)
- `app.py` — Flask app: serves the page and a `/api/solve` JSON endpoint
- `templates/index.html` — page markup, three modes
- `static/style.css` — dark theme, orange accent, JetBrains Mono
- `static/script.js` — tab switching, random draw, calls the API

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000**.

## Modes

1. **4-Digit** — type in four digits and a target by hand.
2. **Random Draw** — same shape, but numbers are rolled for you.
3. **Custom** — add or remove number fields, any target.
