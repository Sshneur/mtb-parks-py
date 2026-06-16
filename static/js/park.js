(async function() {
    const parkId = window.location.pathname.split('/').pop();
    if (!parkId) return;

    // ---------- ЗАГРУЗКА ПОГОДЫ И ГРАФИКИ ----------
    try {
        const weatherResp = await fetch(`/api/park/${parkId}/weather?days=7`);
        if (!weatherResp.ok) throw new Error('Ошибка загрузки погоды');
        const weatherData = await weatherResp.json();
        const daily = weatherData.weather;  // массив из 7 объектов {date, temp_max, rain_total}

        const labels = daily.map(d => {
            const date = new Date(d.date);
            return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
        });
        const temps = daily.map(d => d.temp_max);
        const rains = daily.map(d => d.rain_total);

        // Регистрируем плагин для подписей значений
        Chart.register(ChartDataLabels);

        // График температуры (столбцы с подписями)
        new Chart(document.getElementById('tempChart'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Температура max (°C)',
                    data: temps,
                    backgroundColor: '#e74c3c',
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    datalabels: {
                        anchor: 'end',
                        align: 'top',
                        color: '#fff',
                        font: { weight: 'bold', size: 12 },
                        formatter: (value) => value !== null ? value + '°' : ''
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'День', color: '#aaa' } },
                    y: { title: { display: true, text: '°C', color: '#aaa' }, beginAtZero: true }
                }
            }
        });

        // График осадков (столбцы с подписями)
        new Chart(document.getElementById('rainChart'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Осадки (мм/день)',
                    data: rains,
                    backgroundColor: '#3498db',
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    datalabels: {
                        anchor: 'end',
                        align: 'top',
                        color: '#fff',
                        font: { weight: 'bold', size: 12 },
                        formatter: (value) => value > 0 ? value + 'мм' : ''
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'День', color: '#aaa' } },
                    y: { title: { display: true, text: 'мм', color: '#aaa' }, beginAtZero: true }
                }
            }
        });
    } catch (err) {
        console.error('Ошибка загрузки погоды:', err);
        document.getElementById('park-content').textContent = 'Не удалось загрузить данные погоды.';
    }

    // ---------- СТАТУС ГРУНТА И ТАЙМЕР ----------
    try {
        const statusResp = await fetch(`/api/park/${parkId}/status`);
        if (!statusResp.ok) throw new Error('Ошибка загрузки статуса');
        const status = await statusResp.json();

        document.getElementById('soilStatus').textContent = status.status;
        const timerEl = document.getElementById('dryTimer');
        if (status.dryTarget) {
            function updateTimer() {
                const remaining = status.dryTarget - Date.now();
                if (remaining <= 0) {
                    timerEl.textContent = '';
                    return;
                }
                const sec = Math.floor(remaining / 1000);
                const d = Math.floor(sec / 86400);
                const h = Math.floor((sec % 86400) / 3600);
                const m = Math.floor((sec % 3600) / 60);
                const s = sec % 60;
                const pad = (n) => n < 10 ? '0' + n : n;
                const word = d === 1 ? 'день' : (d < 5 ? 'дня' : 'дней');
                let text = d > 0 ? `${d} ${word} ` : '';
                text += `${pad(h)}:${pad(m)}:${pad(s)}`;
                timerEl.textContent = text;
            }
            updateTimer();
            setInterval(updateTimer, 1000);
        }
    } catch (err) {
        console.error('Ошибка загрузки статуса:', err);
    }

    // ---------- ИСТОРИЯ ГОЛОСОВАНИЙ ----------
    try {
        const historyResp = await fetch(`/api/park/${parkId}/votes-history?days=30`);
        if (historyResp.ok) {
            const historyData = await historyResp.json();
            const history = historyData.history || [];
            const voteDiv = document.getElementById('voteAvg');
            if (history.length > 0) {
                const labels = {1: 'Болото', 2: 'Мокро', 3: 'Альденте', 4: 'Сухо', 5: 'Бетон'};
                let html = '<h3>История народных оценок</h3>';
                html += '<table style="width:100%; border-collapse:collapse;">';
                html += '<tr><th>Дата</th><th>Оценка</th><th>Статус</th><th>Голосов</th></tr>';
                for (const h of history) {
                    const label = labels[Math.round(h.avg)] || '';
                    html += `<tr>
                        <td>${h.date}</td>
                        <td>${h.avg.toFixed(1)}</td>
                        <td>${label}</td>
                        <td>${h.count}</td>
                    </tr>`;
                }
                html += '</table>';
                voteDiv.innerHTML = html;
            } else {
                voteDiv.textContent = 'Народная оценка: пока нет голосов';
            }
        } else {
            document.getElementById('voteAvg').textContent = 'Народная оценка: пока нет голосов';
        }
    } catch (err) {
        console.error('Ошибка загрузки истории голосований:', err);
        document.getElementById('voteAvg').textContent = 'Ошибка загрузки оценок';
    }

    // ---------- ЗАГРУЗКА И ГАЛЕРЕЯ ФОТО ----------
    const photoForm = document.getElementById('photoForm');
    if (photoForm) {
        photoForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById('photoFile');
            const file = fileInput.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const resp = await fetch(`/api/park/${parkId}/photos`, {
                    method: 'POST',
                    body: formData
                });
                if (resp.ok) {
                    fileInput.value = '';
                    loadPhotos();
                } else {
                    alert('Ошибка загрузки фото');
                }
            } catch (err) {
                console.error(err);
                alert('Ошибка загрузки');
            }
        });
    }

    async function loadPhotos() {
        try {
            const resp = await fetch(`/api/park/${parkId}/photos`);
            if (!resp.ok) throw new Error('Ошибка загрузки фото');
            const photos = await resp.json();
            const gallery = document.getElementById('photoGallery');
            gallery.innerHTML = '';
            photos.forEach(p => {
                const card = document.createElement('div');
                card.style.cssText = 'width: 200px; margin-bottom: 15px;';

                const img = document.createElement('img');
                img.src = `/photos/${parkId}/${p.filename}`;
                img.style.cssText = 'width: 100%; height: 200px; object-fit: cover; border-radius: 8px;';

                const info = document.createElement('div');
                info.style.cssText = 'font-size: 12px; color: #aaa; margin-top: 4px; text-align: center;';
                const date = new Date(p.created_at).toLocaleDateString('ru-RU');
                info.textContent = `${date}${p.username ? ', ' + p.username : ''}`;

                card.appendChild(img);
                card.appendChild(info);
                gallery.appendChild(card);
            });
        } catch (err) {
            console.error(err);
        }
    }
    loadPhotos();
})();