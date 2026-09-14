const tabs = document.querySelectorAll('.tab');
const modes = document.querySelectorAll('.mode');
const resultEl = document.getElementById('result');
const resultValue = document.getElementById('result-value');
const resultExpr = document.getElementById('result-expr');
const resultNote = document.getElementById('result-note');

// ---- tab switching ----
tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    tabs.forEach((t) => {
      t.classList.remove('is-active');
      t.setAttribute('aria-selected', 'false');
    });
    tab.classList.add('is-active');
    tab.setAttribute('aria-selected', 'true');

    modes.forEach((m) => m.classList.remove('is-active'));
    document.getElementById(`mode-${tab.dataset.mode}`).classList.add('is-active');

    resultEl.hidden = true;
  });
});

// ---- mode 2: random draw ----
function rollRandom() {
  const digitInputs = document.querySelectorAll('#random-digits .digit-input');
  digitInputs.forEach((input) => {
    input.value = Math.floor(Math.random() * 10);
  });
  document.getElementById('random-target').value = Math.floor(Math.random() * 900) + 100;
}
document.getElementById('roll-btn').addEventListener('click', rollRandom);
rollRandom();

// ---- mode 3: add / remove number fields ----
const customDigits = document.getElementById('custom-digits');
const MAX_CUSTOM = 8;
const MIN_CUSTOM = 2;

document.getElementById('add-number-btn').addEventListener('click', () => {
  if (customDigits.children.length >= MAX_CUSTOM) return;
  const input = document.createElement('input');
  input.type = 'number';
  input.className = 'digit-input';
  input.placeholder = '0';
  customDigits.appendChild(input);
});

document.getElementById('remove-number-btn').addEventListener('click', () => {
  if (customDigits.children.length <= MIN_CUSTOM) return;
  customDigits.removeChild(customDigits.lastElementChild);
});

// ---- solving ----
function collectNumbers(container) {
  return Array.from(container.querySelectorAll('.digit-input'))
    .map((input) => input.value)
    .filter((v) => v !== '')
    .map(Number);
}

function showResult(data) {
  resultEl.hidden = false;

  if (data.error) {
    resultEl.classList.add('is-error');
    resultValue.textContent = 'Error';
    resultExpr.textContent = data.error;
    resultNote.textContent = '';
    return;
  }

  resultEl.classList.remove('is-error');

  if (!data.found) {
    resultValue.textContent = 'No solution found';
    resultExpr.textContent = '';
    resultNote.textContent = 'Nothing landed within ±5 of the target.';
    return;
  }

  resultValue.textContent = data.value;
  resultExpr.textContent = data.expr;
  resultNote.textContent = data.exact
    ? 'Exact match.'
    : `Off by ${data.diff}.`;
}

async function solve(numbers, target) {
  resultEl.hidden = false;
  resultEl.classList.remove('is-error');
  resultValue.textContent = 'Solving…';
  resultExpr.textContent = '';
  resultNote.textContent = '';

  try {
    const res = await fetch('/api/solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ numbers, target }),
    });
    const data = await res.json();
    showResult(data);
  } catch (err) {
    showResult({ error: 'Could not reach the solver.' });
  }
}

document.querySelectorAll('.solve-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const mode = btn.dataset.solveFor;

    let numbers, target;
    if (mode === 'classic') {
      numbers = collectNumbers(document.getElementById('classic-digits'));
      target = Number(document.getElementById('classic-target').value);
    } else if (mode === 'random') {
      numbers = collectNumbers(document.getElementById('random-digits'));
      target = Number(document.getElementById('random-target').value);
    } else {
      numbers = collectNumbers(document.getElementById('custom-digits'));
      target = Number(document.getElementById('custom-target').value);
    }

    if (numbers.length === 0 || !target) {
      showResult({ error: 'Fill in the numbers and a target first.' });
      return;
    }

    solve(numbers, target);
  });
});
