(async function() {
    const parkId = window.location.pathname.split('/').pop();
    if (!parkId) return;

    // ---------- ПРОВЕРКА АВТОРИЗАЦИИ ----------
    const token = localStorage.getItem('token') || '';
    let currentUser = null;

    async function loadUser() {
        if (!token) return;
        try {
            const res = await fetch('/api/user/me', { headers: { 'Authorization': 'Bearer ' + token } });
            if (res.ok) {
                currentUser = await res.json();
                document.getElementById('authMessage').style.display = 'none';
                document.getElementById('photoForm').style.display = 'block';
            } else {
                document.getElementById('authMessage').style.display = 'block';
                document.getElementById('photoForm').style.display = 'none';
            }
        } catch(e) {
            document.getElementById('authMessage').style.display = 'block';
            document.getElementById('photoForm').style.display = 'none';
        }
    }
    await loadUser();

    // ---------- ВЫБОР ОЦЕНКИ ----------
    const voteButtons = document.querySelectorAll('.vote-btn');
    let selectedVote = null;

    voteButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            voteButtons.forEach(b => {
                b.style.borderColor = '#555';
                b.style.background = 'transparent';
            });
            this.style.borderColor = '#74a8e2';
            this.style.background = 'rgba(74, 144, 226, 0.2)';
            selectedVote = parseInt(this.dataset.vote);
            document.getElementById('selectedVote').value = selectedVote;
        });
    });

    // ---------- ЗАГРУЗКА ПОГОДЫ И ГРАФИКИ ----------
    try {
        const weatherResp = await fetch(`/api/park/${parkId}/weather?days=7`);
        if (!weatherResp.ok) throw new Error('Ошибка загрузки погоды');
        const weatherData = await weatherResp.json();
        const daily = weatherData.weather;

        const labels = daily.map(d => {
            const date = new Date(d.date);
            return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
        });
        const temps = daily.map(d => d.temp_max);
        const rains = daily.map(d => d.rain_total);

        Chart.register(ChartDataLabels);

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

    // ---------- СРЕДНЯЯ ОЦЕНКА (ВМЕСТО ИСТОРИИ) ----------
    try {
        const voteResp = await fetch(`/api/park/${parkId}/votes-history`);
        if (voteResp.ok) {
            const data = await voteResp.json();
            const voteDiv = document.getElementById('voteAvg');
            if (data.avg !== null && data.avg !== undefined && data.count > 0) {
                const labels = {1: '🌿 Болото', 2: '💧 Мокро', 3: '🌵 Альденте', 4: '✅ Сухо', 5: '🪨 Бетон'};
                const rounded = Math.round(data.avg);
                const label = labels[rounded] || '';
                voteDiv.innerHTML = `
                    <div style="margin:10px 0; padding:12px; background:rgba(0,20,40,0.7); border-radius:12px; text-align:center;">
                        <div style="font-size:1.2rem; font-weight:600; color:#ffd966;">
                            ⭐ Средняя оценка: ${data.avg.toFixed(1)} (${data.count} голосов)
                        </div>
                        <div style="font-size:1.1rem; color:#b8d6ff;">${label}</div>
                    </div>
                `;
            } else {
                voteDiv.innerHTML = `
                    <div style="margin:10px 0; padding:12px; background:rgba(0,20,40,0.7); border-radius:12px; text-align:center; color:#94afcf;">
                        📸 Пока нет оценок. Загрузите фото с оценкой!
                    </div>
                `;
            }
        } else {
            document.getElementById('voteAvg').textContent = 'Ошибка загрузки оценок';
        }
    } catch (err) {
        console.error('Ошибка загрузки средней оценки:', err);
        document.getElementById('voteAvg').textContent = 'Ошибка загрузки оценок';
    }

    // ---------- ЗАГРУЗКА ФОТО ----------
    const submitBtn = document.getElementById('photoSubmitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            const fileInput = document.getElementById('photoFile');
            const file = fileInput.files[0];
            if (!file) {
                alert('Выберите файл');
                return;
            }

            const vote = document.getElementById('selectedVote').value;
            if (!vote) {
                alert('Пожалуйста, выберите оценку состояния грунта');
                return;
            }

            const formData = new FormData();
            formData.append('file', file, file.name);
            formData.append('vote', vote);

            const statusDiv = document.getElementById('uploadStatus');
            statusDiv.textContent = '⏳ Загрузка...';
            statusDiv.style.color = '#ffd966';

            try {
                const resp = await fetch(`/api/park/${parkId}/photos`, {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token },
                    body: formData
                });

                if (resp.ok) {
                    const data = await resp.json();
                    statusDiv.textContent = '✅ Фото загружено! Оценка: ' + vote;
                    statusDiv.style.color = '#4caf50';
                    fileInput.value = '';
                    voteButtons.forEach(b => {
                        b.style.borderColor = '#555';
                        b.style.background = 'transparent';
                    });
                    document.getElementById('selectedVote').value = '';
                    selectedVote = null;
                    loadPhotos();
                    // Обновляем среднюю оценку после загрузки
                    fetchAverageVote();
                } else {
                    const errText = await resp.text();
                    statusDiv.textContent = '❌ Ошибка сервера: ' + resp.status + ' ' + errText;
                    statusDiv.style.color = '#ff6b6b';
                }
            } catch (err) {
                statusDiv.textContent = '❌ Ошибка сети: ' + err.message;
                statusDiv.style.color = '#ff6b6b';
            }
        });
    }

    // ---------- ЗАГРУЗКА ГАЛЕРЕИ ----------
    async function loadPhotos() {
        try {
            const resp = await fetch(`/api/park/${parkId}/photos`);
            if (!resp.ok) throw new Error('Ошибка загрузки фото');
            const photos = await resp.json();
            const gallery = document.getElementById('photoGallery');
            gallery.innerHTML = '';

            if (photos.length === 0) {
                gallery.innerHTML = '<p style="color:#aaa;">Фото пока нет. Будьте первым!</p>';
                return;
            }

            const voteLabels = {
                1: '🌿 Болото',
                2: '💧 Мокро',
                3: '🌵 Альденте',
                4: '✅ Сухо',
                5: '🪨 Бетон'
            };

            photos.forEach(p => {
                const card = document.createElement('div');
                card.style.cssText = 'background: rgba(18,22,30,0.85); border-radius:12px; padding:10px; border:1px solid rgba(74,144,226,0.2);';

                const img = document.createElement('img');
                img.src = `/photos/${parkId}/${p.filename}`;
                img.style.cssText = 'width:100%; aspect-ratio:1/1; object-fit:cover; border-radius:8px;';

                const info = document.createElement('div');
                info.style.cssText = 'margin-top:8px; font-size:13px; color:#ddd; text-align:center;';

                const date = new Date(p.created_at).toLocaleDateString('ru-RU', { day:'numeric', month:'long', year:'numeric' });
                const username = p.username || 'Аноним';
                const voteText = p.vote ? voteLabels[p.vote] || p.vote : '—';

                info.innerHTML = `
                    <div><strong>${username}</strong></div>
                    <div style="font-size:12px; color:#aaa;">${date}</div>
                    <div style="font-size:14px; font-weight:bold; color:#74a8e2;">${voteText}</div>
                `;

                card.appendChild(img);
                card.appendChild(info);
                gallery.appendChild(card);
            });
        } catch (err) {
            console.error('Ошибка загрузки фото:', err);
        }
    }

    // ---------- ОБНОВЛЕНИЕ СРЕДНЕЙ ОЦЕНКИ (для вызова после загрузки фото) ----------
    async function fetchAverageVote() {
        try {
            const resp = await fetch(`/api/park/${parkId}/votes-history`);
            if (resp.ok) {
                const data = await resp.json();
                const voteDiv = document.getElementById('voteAvg');
                if (data.avg !== null && data.avg !== undefined && data.count > 0) {
                    const labels = {1: '🌿 Болото', 2: '💧 Мокро', 3: '🌵 Альденте', 4: '✅ Сухо', 5: '🪨 Бетон'};
                    const rounded = Math.round(data.avg);
                    const label = labels[rounded] || '';
                    voteDiv.innerHTML = `
                        <div style="margin:10px 0; padding:12px; background:rgba(0,20,40,0.7); border-radius:12px; text-align:center;">
                            <div style="font-size:1.2rem; font-weight:600; color:#ffd966;">
                                ⭐ Средняя оценка: ${data.avg.toFixed(1)} (${data.count} голосов)
                            </div>
                            <div style="font-size:1.1rem; color:#b8d6ff;">${label}</div>
                        </div>
                    `;
                } else {
                    voteDiv.innerHTML = `
                        <div style="margin:10px 0; padding:12px; background:rgba(0,20,40,0.7); border-radius:12px; text-align:center; color:#94afcf;">
                            📸 Пока нет оценок. Загрузите фото с оценкой!
                        </div>
                    `;
                }
            }
        } catch (e) {
            console.error('Ошибка обновления оценки:', e);
        }
    }

    loadPhotos();
})();