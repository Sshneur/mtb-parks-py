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

        const maxTemp = Math.max(...temps, 0);
        new Chart(document.getElementById('tempChart'), {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Температура max (°C)',
                    data: temps,
                    borderColor: '#ff6b35',
                    backgroundColor: (ctx) => {
                        if (!ctx.chart.chartArea) return 'transparent';
                        const g = ctx.chart.ctx.createLinearGradient(0, ctx.chart.chartArea.top, 0, ctx.chart.chartArea.bottom);
                        g.addColorStop(0, 'rgba(255,107,53,0.35)');
                        g.addColorStop(1, 'rgba(255,107,53,0.02)');
                        return g;
                    },
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#ff6b35',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 20 } },
                plugins: {
                    legend: { display: false },
                    datalabels: {
                        anchor: 'end',
                        align: 'end',
                        offset: 2,
                        color: '#ffd966',
                        font: { weight: 'bold', size: 11 },
                        formatter: (value) => value !== null ? value + '°' : ''
                    }
                },
                scales: {
                    x: { ticks: { color: '#94afcf' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: {
                        min: 0,
                        max: Math.max(maxTemp + 8, 10),
                        ticks: { color: '#94afcf', stepSize: 5 },
                        grid: { color: 'rgba(255,255,255,0.08)' }
                    }
                }
            }
        });

        const maxRain = Math.max(...rains, 0);
        new Chart(document.getElementById('rainChart'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Осадки (мм/день)',
                    data: rains,
                    backgroundColor: (ctx) => {
                        if (!ctx.chart.chartArea) return 'rgba(52,152,219,0.6)';
                        const g = ctx.chart.ctx.createLinearGradient(0, ctx.chart.chartArea.top, 0, ctx.chart.chartArea.bottom);
                        g.addColorStop(0, 'rgba(52,152,219,0.85)');
                        g.addColorStop(1, 'rgba(52,152,219,0.3)');
                        return g;
                    },
                    borderRadius: 6,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 20 } },
                plugins: {
                    legend: { display: false },
                    datalabels: {
                        anchor: 'end',
                        align: 'end',
                        offset: 2,
                        color: '#74b9ff',
                        font: { weight: 'bold', size: 11 },
                        formatter: (value) => value > 0 ? value + 'мм' : ''
                    }
                },
                scales: {
                    x: { ticks: { color: '#94afcf' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: {
                        beginAtZero: true,
                        max: maxRain > 0 ? maxRain * 1.4 : 5,
                        ticks: { color: '#94afcf' },
                        grid: { color: 'rgba(255,255,255,0.08)' }
                    }
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

        const statusEl = document.getElementById('soilStatus');
        statusEl.textContent = status.status;
        const statusColors = {'Сухо':'#4caf50','Альденте':'#26c6da','Мокро':'#2196f3','Болото':'#795548','Бетон':'#9e9e9e'};
        const color = Object.keys(statusColors).find(k => status.status.includes(k));
        if (color) {
            statusEl.style.color = statusColors[color];
            document.getElementById('statusCard').style.borderColor = statusColors[color] + '66';
        }
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

            const comment = document.getElementById('photoComment').value.trim();

            const statusDiv = document.getElementById('uploadStatus');
            statusDiv.textContent = '⏳ Загрузка...';
            statusDiv.style.color = '#ffd966';

            try {
                // Read file as base64 (workaround for Safari FormData bug)
                const reader = new FileReader();
                const fileData = await new Promise((resolve, reject) => {
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = () => reject('Ошибка чтения файла');
                    reader.readAsDataURL(file);
                });

                const resp = await fetch(`/api/park/${parkId}/photos`, {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        file: fileData,
                        name: file.name,
                        vote: parseInt(vote),
                        comment: comment || ''
                    })
                });

                if (resp.ok) {
                    const data = await resp.json();
                    statusDiv.textContent = '✅ Фото загружено! Оценка: ' + vote;
                    statusDiv.style.color = '#4caf50';
                    fileInput.value = '';
                    document.getElementById('photoComment').value = '';
                    voteButtons.forEach(b => {
                        b.style.borderColor = '#555';
                        b.style.background = 'transparent';
                    });
                    document.getElementById('selectedVote').value = '';
                    selectedVote = null;
                    loadPhotos();
                    fetchAverageVote();
                } else {
                    const errText = await resp.text();
                    statusDiv.textContent = '❌ Ошибка сервера: ' + resp.status + ' ' + errText;
                    statusDiv.style.color = '#ff6b6b';
                }
            } catch (err) {
                statusDiv.textContent = '❌ Ошибка сети: ' + err;
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
                img.style.cssText = 'width:100%; aspect-ratio:1/1; object-fit:cover; border-radius:8px; cursor:pointer; transition:transform 0.2s;';
                img.onmouseenter = function() { this.style.transform = 'scale(1.03)'; };
                img.onmouseleave = function() { this.style.transform = 'scale(1)'; };
                img.onclick = function() {
                    const lightbox = document.getElementById('lightbox');
                    const lightboxImg = document.getElementById('lightboxImg');
                    lightboxImg.src = this.src;
                    lightbox.style.display = 'flex';
                };

                const info = document.createElement('div');
                info.style.cssText = 'margin-top:8px; font-size:13px; color:#ddd; text-align:center;';

                const date = new Date(p.created_at).toLocaleDateString('ru-RU', { day:'numeric', month:'long', year:'numeric' });
                const username = p.username || 'Аноним';
                const voteText = p.vote ? voteLabels[p.vote] || p.vote : '—';

                const commentText = p.comment ? `<div style="font-size:12px; color:#aaa; margin-top:4px;">💬 ${p.comment}</div>` : '';
                info.innerHTML = `
                    <div><strong>${username}</strong></div>
                    <div style="font-size:12px; color:#aaa;">${date}</div>
                    <div style="font-size:14px; font-weight:bold; color:#74a8e2;">${voteText}</div>
                    ${commentText}
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

    // ---------- ПРОГНОЗ ГРУНТА — горизонтальный свайп ----------
    (async function loadForecast() {
        try {
            const resp = await fetch(`/api/park/${parkId}/soil-forecast`);
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.forecast || data.forecast.length === 0) return;

            const box = document.getElementById('forecastBox');
            const grid = document.getElementById('forecastGrid');
            const bestEl = document.getElementById('forecastBest');
            box.style.display = 'block';
            grid.innerHTML = '';

            const soilViz = {
                'сухо':     { color:'#4caf50', bg:'rgba(76,175,80,0.15)', icon:'✓' },
                'альденте': { color:'#26c6da', bg:'rgba(38,198,218,0.12)', icon:'~' },
                'мокро':    { color:'#2196f3', bg:'rgba(33,150,243,0.12)', icon:'≈' },
                'болото':   { color:'#795548', bg:'rgba(121,85,56,0.15)', icon:'≡' },
            };

            // horizontal scroll container
            const scroller = document.createElement('div');
            scroller.style.cssText = 'display:flex; overflow-x:auto; scroll-snap-type:x mandatory; -webkit-overflow-scrolling:touch; gap:0; scroll-behavior:smooth; padding:2px 0 8px;';
            scroller.id = 'forecastScroller';

            // nav dots container
            const dotsWrap = document.createElement('div');
            dotsWrap.style.cssText = 'display:flex; justify-content:center; gap:8px; margin-top:6px;';

            let bestOverall = null;

            data.forecast.forEach((day, idx) => {
                // scroller page
                const page = document.createElement('div');
                page.style.cssText = 'scroll-snap-align:start; flex:0 0 100%; background:rgba(18,22,30,0.85); border:1px solid rgba(255,255,255,0.08); border-radius:18px; padding:20px 16px;';
                page.id = 'forecastPage' + idx;

                const dateObj = new Date(day.date + 'T12:00:00+03:00');
                const dayLabel = dateObj.toLocaleDateString('ru-RU', { weekday:'short', day:'numeric', month:'short' });

                const header = document.createElement('div');
                header.textContent = dayLabel;
                header.style.cssText = 'font-size:1.35rem; font-weight:700; color:#ffd966; text-align:center; padding-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:10px;';
                page.appendChild(header);

                if (!day.periods || day.periods.length === 0) {
                    const empty = document.createElement('div');
                    empty.textContent = 'Нет данных на этот день';
                    empty.style.cssText = 'font-size:0.85rem; color:#556677; text-align:center; padding:20px 0;';
                    page.appendChild(empty);
                    scroller.appendChild(page);
                    // dot
                    const dot = document.createElement('div');
                    dot.style.cssText = 'width:8px; height:8px; border-radius:50%; background:rgba(255,255,255,0.3); cursor:pointer;';
                    dotsWrap.appendChild(dot);
                    return;
                }

                day.periods.forEach(p => {
                    const viz = soilViz[p.soil] || soilViz['сухо'];
                    const card = document.createElement('div');
                    card.style.cssText = `border-radius:14px; padding:14px 12px; margin-bottom:10px; background:${viz.bg}; border-left:5px solid ${viz.color};`;

                    card.innerHTML = `
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:1.1rem; font-weight:600; color:#eef5ff;">${p.label}</span>
                            <span style="display:inline-flex; align-items:center; gap:8px; font-size:0.95rem; color:${viz.color}; font-weight:600;">
                                <span style="display:inline-flex; justify-content:center; align-items:center; width:28px; height:28px; border-radius:50%; background:${viz.color}; color:#0b0d14; font-size:0.85rem; font-weight:700;">${viz.icon}</span>
                                ${p.soil}
                            </span>
                        </div>
                        <div style="display:flex; gap:20px; font-size:0.95rem; color:#8899aa;">
                            <span>🌡 ${p.temp}°C</span>
                            <span>💨 ${p.wind} м/с</span>
                            <span>🌧 ${p.rain} мм</span>
                        </div>
                    `;
                    page.appendChild(card);

                    if (!bestOverall || (p.confidence > bestOverall.confidence && p.soil !== 'мокро' && p.soil !== 'болото')) {
                        bestOverall = p;
                        bestOverall.dayLabel = dayLabel;
                    }
                });

                scroller.appendChild(page);

                // nav dot
                const dot = document.createElement('div');
                dot.style.cssText = `width:8px; height:8px; border-radius:50%; background:${idx===0?'#ffd966':'rgba(255,255,255,0.25)'}; cursor:pointer; transition:background 0.2s;`;
                dot.dataset.index = idx;
                dot.addEventListener('click', () => {
                    const target = document.getElementById('forecastPage' + idx);
                    if (target) target.scrollIntoView({ behavior:'smooth', inline:'start' });
                });
                dotsWrap.appendChild(dot);
            });

            grid.appendChild(scroller);
            grid.appendChild(dotsWrap);

            // update active dot on scroll
            scroller.addEventListener('scroll', () => {
                const pages = scroller.querySelectorAll('[id^="forecastPage"]');
                const dots = dotsWrap.children;
                let active = 0;
                const scrollLeft = scroller.scrollLeft + scroller.clientWidth / 2;
                pages.forEach((p, i) => {
                    const rect = p.getBoundingClientRect();
                    const containerRect = scroller.getBoundingClientRect();
                    if (rect.left <= containerRect.left + containerRect.width / 2) {
                        active = i;
                    }
                });
                for (let i = 0; i < dots.length; i++) {
                    dots[i].style.background = i === active ? '#ffd966' : 'rgba(255,255,255,0.25)';
                }
            });

            if (bestOverall) {
                bestEl.innerHTML = `⭐ Лучшее время старта: <strong>${bestOverall.dayLabel}, ${bestOverall.label}</strong> — ${bestOverall.soil}, +${bestOverall.temp}°C, ветер ${bestOverall.wind} м/с`;
                bestEl.style.cssText = 'margin-top:12px; font-size:1rem; color:#a0b4cc; text-align:center; padding:8px;';
            }
        } catch (e) {
            console.error('Ошибка прогноза:', e);
        }
    })();

    loadPhotos();
})();