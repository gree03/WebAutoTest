document.addEventListener('DOMContentLoaded', () => {
  const output      = document.getElementById('output');
  const progressBar = document.getElementById('progressBar');
  const timerEl     = document.getElementById('timer');
  let timerInterval;

  function startTimer() {
    const start = Date.now();
    if (timerEl) {
      timerEl.textContent = '00:00';
    }
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      const diff = Math.floor((Date.now() - start) / 1000);
      const m = Math.floor(diff / 60).toString().padStart(2, '0');
      const s = (diff % 60).toString().padStart(2, '0');
      if (timerEl) {
        timerEl.textContent = `${m}:${s}`;
      }
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerInterval);
  }

  // Start 1
  const start1Btn = document.getElementById('start1Btn');
  if (start1Btn) {
    start1Btn.addEventListener('click', () => {
      progressBar.value = 0;
      output.textContent = '';
      startTimer();

      const evt1 = new EventSource('/start1_progress');
      evt1.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (msg.progress !== undefined) {
          progressBar.value = msg.progress;
        }
        if (msg.done) {
          output.textContent = msg.result;
          stopTimer();
          evt1.close();
        }
      };
      evt1.onerror = () => {
        output.textContent = 'Ошибка соединения Старт 1.';
        stopTimer();
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
      startTimer();

      const evt2 = new EventSource('/start2_progress');
      evt2.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (msg.progress !== undefined) {
          progressBar.value = msg.progress;
        }
        if (msg.done) {
          output.textContent = msg.result;
          stopTimer();
          evt2.close();
        }
      };
      evt2.onerror = () => {
        output.textContent = 'Ошибка соединения Старт 2.';
        stopTimer();
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
    startTimer();

    const evt3 = new EventSource('/start3_progress');
    evt3.onmessage = e => {
      const msg = JSON.parse(e.data);
      if (msg.progress !== undefined) {
        progressBar.value = msg.progress;
      }
      if (msg.done) {
        output.textContent = msg.result;
        stopTimer();
        evt3.close();
      }
    };
    evt3.onerror = () => {
      output.textContent = 'Ошибка соединения Старт 3.';
      stopTimer();
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
