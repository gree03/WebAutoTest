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

  // ================= CONFIG EDITOR =================
  const configDataEl = document.getElementById('config-data');
  const doorphonesEl = document.getElementById('doorphones');

  if (configDataEl && doorphonesEl) {
    const initialConfig = JSON.parse(configDataEl.textContent || '""');

    function createVarRow(name = '', value = '') {
      const row = document.createElement('div');
      row.className = 'var-row';

      const nameInput = document.createElement('input');
      nameInput.type = 'text';
      nameInput.className = 'var-name';
      nameInput.value = name;

      const valueInput = document.createElement('input');
      valueInput.type = 'text';
      valueInput.className = 'var-value';
      valueInput.value = value;

      const del = document.createElement('span');
      del.textContent = '🗑️';
      del.className = 'delete-var';
      del.addEventListener('click', () => row.remove());

      row.appendChild(nameInput);
      row.appendChild(valueInput);
      row.appendChild(del);
      return row;
    }

    function createDoorphoneBlock() {
      const block = document.createElement('div');
      block.className = 'doorphone-block';
      doorphonesEl.appendChild(block);
      return block;
    }

    // Parse initial config
    let currentBlock = createDoorphoneBlock();
    initialConfig.split(/\r?\n/).forEach(line => {
      const trimmed = line.trim();
      if (!trimmed) return;
      if (trimmed === '__________________') {
        currentBlock = createDoorphoneBlock();
      } else {
        const idx = trimmed.indexOf('=');
        if (idx !== -1) {
          const name = trimmed.slice(0, idx).trim();
          const value = trimmed.slice(idx + 1).trim();
          currentBlock.appendChild(createVarRow(name, value));
        }
      }
    });

    const addVarBtn = document.getElementById('addVarBtn');
    addVarBtn.addEventListener('click', () => {
      let blocks = doorphonesEl.getElementsByClassName('doorphone-block');
      if (blocks.length === 0) {
        currentBlock = createDoorphoneBlock();
      } else {
        currentBlock = blocks[blocks.length - 1];
      }
      currentBlock.appendChild(createVarRow());
    });

    const addDoorphoneBtn = document.getElementById('addDoorphoneBtn');
    addDoorphoneBtn.addEventListener('click', () => {
      currentBlock = createDoorphoneBlock();
    });

    const form = document.getElementById('configForm');
    form.addEventListener('submit', () => {
      const blocks = doorphonesEl.getElementsByClassName('doorphone-block');
      let lines = [];
      for (let i = 0; i < blocks.length; i++) {
        const rows = blocks[i].querySelectorAll('.var-row');
        rows.forEach(row => {
          const n = row.querySelector('.var-name').value.trim();
          const v = row.querySelector('.var-value').value.trim();
          if (n) {
            lines.push(n + '=' + v);
          }
        });
        if (i < blocks.length - 1) {
          lines.push('__________________');
        }
      }
      document.getElementById('configInput').value = lines.join('\n');
    });
  }

});
