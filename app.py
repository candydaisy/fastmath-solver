"""
FastMath web app.

Run with:
    python app.py

Then open http://localhost:5000 in a browser.
"""

from flask import Flask, render_template, request, jsonify

from solver import solve_numbers

app = Flask(__name__)

MAX_NUMBERS = 8


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/solve", methods=["POST"])
def api_solve():
    data = request.get_json(silent=True) or {}
    numbers = data.get("numbers")
    target = data.get("target")

    if not isinstance(numbers, list) or not (1 <= len(numbers) <= MAX_NUMBERS):
        return jsonify(error=f"Send between 1 and {MAX_NUMBERS} numbers."), 400

    try:
        numbers = [int(n) for n in numbers]
        target = int(target)
    except (TypeError, ValueError):
        return jsonify(error="Numbers and target must be integers."), 400

    if target <= 0:
        return jsonify(error="Target must be a positive integer."), 400

    value, expr, diff = solve_numbers(numbers, target)

    if value is None:
        return jsonify(found=False)

    return jsonify(
        found=True,
        value=value,
        expr=expr,
        diff=diff,
        exact=(diff == 0),
    )


if __name__ == "__main__":
    app.run(debug=True)
