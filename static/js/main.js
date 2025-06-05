document.addEventListener('DOMContentLoaded', () => {
  const output      = document.getElementById('output');
  const progressBar = document.getElementById('progressBar');

  // Start 1
  const start1Btn = document.getElementById('start1Btn');
  if (start1Btn) {
    start1Btn.addEventListener('click', () => {
      progressBar.value = 0;
      output.textContent = '';

      const evt1 = new EventSource('/start1_progress');
      evt1.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (msg.progress !== undefined) {
          progressBar.value = msg.progress;
        }
        if (msg.done) {
          output.textContent = msg.result;
          evt1.close();
        }
      };
      evt1.onerror = () => {
        output.textContent = 'Ошибка соединения Старт 1.';
        evt1.close();
      };
    });
  }

  // Start 2
  const start2Btn = document.getElementById('start2Btn');
  if (start2Btn) {
    start2Btn.addEventListener('click', () => {
      progressBar.value = 0;
      output.textContent = '';

      const evt2 = new EventSource('/start2_progress');
      evt2.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (msg.progress !== undefined) {
          progressBar.value = msg.progress;
        }
        if (msg.done) {
          output.textContent = msg.result;
          evt2.close();
        }
      };
      evt2.onerror = () => {
        output.textContent = 'Ошибка соединения Старт 2.';
        evt2.close();
      };
    });
  }

// Start 3
const start3Btn = document.getElementById('start3Btn');
if (start3Btn) {
  start3Btn.addEventListener('click', () => {
    progressBar.value = 0;
    output.textContent = '';

    const evt3 = new EventSource('/start3_progress');
    evt3.onmessage = e => {
      const msg = JSON.parse(e.data);
      if (msg.progress !== undefined) {
        progressBar.value = msg.progress;
      }
      if (msg.done) {
        output.textContent = msg.result;
        evt3.close();
      }
    };
    evt3.onerror = () => {
      output.textContent = 'Ошибка соединения Старт 3.';
      evt3.close();
    };
  });
}

  // Result
  const resultBtn = document.getElementById('resultBtn');
  if (resultBtn) {
    resultBtn.addEventListener('click', () => {
      progressBar.value = 0;
      output.textContent = '';
      fetch('/result')
        .then(res => res.json())
        .then(data => {
          // В этом случае прогресс не меняется, сразу выводим результат
          output.textContent = data.result;
        })
        .catch(() => {
          output.textContent = 'Ошибка при получении результата.';
        });
    });
  }
});
