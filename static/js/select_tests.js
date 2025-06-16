document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('tests-form');
  const output = document.getElementById('custom-output');
  if (!form) return;
  form.addEventListener('submit', evt => {
    evt.preventDefault();
    output.textContent = 'Выполнение...';
    const checked = Array.from(form.querySelectorAll('input[name="tests"]:checked')).map(el => el.value);
    fetch('/api/run-tests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tests: checked })
    })
    .then(r => r.json())
    .then(data => {
      output.textContent = data.result || 'Нет результата';
    })
    .catch(() => {
      output.textContent = 'Ошибка запуска';
    });
  });
});
