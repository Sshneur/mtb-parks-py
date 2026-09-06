(async function() {
    const parkId = window.location.pathname.split('/').pop();
    if (!parkId) return;
    if (window.umami) umami.track('park_detail_view', { park_id: parkId });

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
                b.classList.remove('vote-btn-selected');
            });
            this.classList.add('vote-btn-selected');
            selectedVote = parseInt(this.dataset.vote);
            document.getElementById('selectedVote').value = selectedVote;
            if (window.umami) umami.track('vote_submit', { park_id: parkId, vote: selectedVote });
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

        function chartTheme() {
            var light = document.documentElement.classList.contains('theme-light');
            return {
                tick: light ? '#4b5563' : '#8b949e',
                grid: light ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.08)',
                text: light ? '#1a1e2b' : '#eef5ff',
                accent: light ? '#4a90e2' : '#74b9ff'
            };
        }

        var t = chartTheme();

        const maxTemp = Math.max(...temps, 0);
        var tempChart = new Chart(document.getElementById('tempChart'), {
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
                        color: t.text,
                        font: { weight: 'bold', size: 11 },
                        formatter: (value) => value !== null ? value + '°' : ''
                    }
                },
                scales: {
                    x: { ticks: { color: t.tick }, grid: { color: t.grid } },
                    y: {
                        min: 0,
                        max: Math.max(maxTemp + 8, 10),
                        ticks: { color: t.tick, stepSize: 5 },
                        grid: { color: t.grid }
                    }
                }
            }
        });

        const maxRain = Math.max(...rains, 0);
        var rainChart = new Chart(document.getElementById('rainChart'), {
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
                        color: t.accent,
                        font: { weight: 'bold', size: 11 },
                        formatter: (value) => value > 0 ? value + 'мм' : ''
                    }
                },
                scales: {
                    x: { ticks: { color: t.tick }, grid: { color: t.grid } },
                    y: {
                        beginAtZero: true,
                        max: maxRain > 0 ? maxRain * 1.4 : 5,
                        ticks: { color: t.tick },
                        grid: { color: t.grid }
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
                    <div class="vote-box">
                        <div class="vote-box-title">
                            ⭐ Средняя оценка: ${data.avg.toFixed(1)} (${data.count} голосов)
                        </div>
                        <div class="vote-box-status">${label}</div>
                    </div>
                `;
            } else {
                voteDiv.innerHTML = `
                    <div class="vote-box" style="color:var(--text-muted);">
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
                    if (window.umami) umami.track('photo_upload', { park_id: parkId, vote: parseInt(vote), has_comment: comment.length > 0 });
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

    // ---------- ЗАГРУЗКА ГАЛЕРЕИ (ленивая, по 10) ----------
    var photoOffset = 0;
    var photoHasMore = false;
    var photoLoading = false;

    async function loadPhotos(reset) {
        if (reset === undefined) reset = true;
        if (photoLoading) return;
        photoLoading = true;
        try {
            if (reset) {
                photoOffset = 0;
                document.getElementById('photoGallery').innerHTML = '';
                document.getElementById('photoGallery').dataset.page = 'loading';
            }
            const resp = await fetch(`/api/park/${parkId}/photos?limit=10&offset=${photoOffset}`);
            if (!resp.ok) throw new Error('Ошибка загрузки фото');
            const data = await resp.json();
            const photos = data.photos;
            const gallery = document.getElementById('photoGallery');

            if (reset && photos.length === 0) {
                gallery.innerHTML = '<p class="photo-empty">Фото пока нет. Будьте первым!</p>';
                delete gallery.dataset.page;
                photoLoading = false;
                return;
            }

            // Удаляем старую кнопку "Показать ещё"
            var oldBtn = gallery.querySelector('.load-more-btn');
            if (oldBtn) oldBtn.remove();

            const voteLabels = {
                1: '🌿 Болото',
                2: '💧 Мокро',
                3: '🌵 Альденте',
                4: '✅ Сухо',
                5: '🪨 Бетон'
            };

            photos.forEach(function(p) {
                var card = document.createElement('div');
                card.className = 'photo-card';

                var img = document.createElement('img');
                img.src = '/photos/' + parkId + '/' + p.filename;
                img.className = 'photo-img';
                img.onmouseenter = function() { this.style.transform = 'scale(1.03)'; };
                img.onmouseleave = function() { this.style.transform = 'scale(1)'; };
                img.onclick = function() {
                    var lightbox = document.getElementById('lightbox');
                    var lightboxImg = document.getElementById('lightboxImg');
                    lightboxImg.src = this.src;
                    lightbox.style.display = 'flex';
                    if (window.umami) umami.track('photo_lightbox', { park_id: parkId });
                };

                var info = document.createElement('div');
                info.className = 'photo-info';

                var date = new Date(p.created_at).toLocaleDateString('ru-RU', { day:'numeric', month:'long', year:'numeric' });
                var username = p.username || 'Аноним';
                var voteText = p.vote ? voteLabels[p.vote] || p.vote : '—';

                var nameDiv = document.createElement('div');
                var strong = document.createElement('strong');
                strong.textContent = username;
                nameDiv.appendChild(strong);
                var dateDiv = document.createElement('div');
                dateDiv.className = 'photo-date';
                dateDiv.textContent = date;
                var voteDiv = document.createElement('div');
                voteDiv.className = 'photo-vote';
                voteDiv.textContent = voteText;
                info.appendChild(nameDiv);
                info.appendChild(dateDiv);
                info.appendChild(voteDiv);
                if (p.comment) {
                    var commentDiv = document.createElement('div');
                    commentDiv.className = 'photo-comment';
                    commentDiv.textContent = '💬 ' + p.comment;
                    info.appendChild(commentDiv);
                }

                card.appendChild(img);
                card.appendChild(info);
                gallery.appendChild(card);
            });

            photoHasMore = data.hasMore;
            if (photoHasMore) {
                var loadMore = document.createElement('button');
                loadMore.className = 'load-more-btn';
                loadMore.textContent = '📷 Показать ещё (' + (data.total - photoOffset - photos.length) + ')';
                loadMore.className = 'load-more-btn';
                loadMore.onclick = function() {
                    photoOffset += 10;
                    if (window.umami) umami.track('photo_load_more', { park_id: parkId, offset: photoOffset });
                    loadPhotos(false);
                };
                gallery.appendChild(loadMore);
            }

            delete gallery.dataset.page;
        } catch (err) {
            console.error('Ошибка загрузки фото:', err);
        }
        photoLoading = false;
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
                        <div class="vote-box">
                            <div class="vote-box-title">
                                ⭐ Средняя оценка: ${data.avg.toFixed(1)} (${data.count} голосов)
                            </div>
                            <div class="vote-box-status">${label}</div>
                        </div>
                    `;
                } else {
                    voteDiv.innerHTML = `
                        <div class="vote-box" style="color:var(--text-muted);">
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
                page.className = 'forecast-page';
                page.id = 'forecastPage' + idx;

                const dateObj = new Date(day.date + 'T12:00:00+03:00');
                const dayLabel = dateObj.toLocaleDateString('ru-RU', { weekday:'short', day:'numeric', month:'short' });

                const header = document.createElement('div');
                header.textContent = dayLabel;
                header.className = 'forecast-page-header';
                page.appendChild(header);

                if (!day.periods || day.periods.length === 0) {
                    const empty = document.createElement('div');
                    empty.textContent = 'Нет данных на этот день';
                    empty.className = 'forecast-empty';
                    page.appendChild(empty);
                    scroller.appendChild(page);
                    // dot
                    const dot = document.createElement('div');
                    dot.className = 'forecast-dot forecast-dot-inactive';
                    dotsWrap.appendChild(dot);
                    return;
                }

                day.periods.forEach(p => {
                    const viz = soilViz[p.soil] || soilViz['сухо'];
                    const card = document.createElement('div');
                    card.style.cssText = `border-radius:14px; padding:14px 12px; margin-bottom:10px; background:${viz.bg}; border-left:5px solid ${viz.color};`;

                    card.innerHTML = `
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span class="forecast-label">${p.label}</span>
                            <span style="display:inline-flex; align-items:center; gap:8px; font-size:0.95rem; color:${viz.color}; font-weight:600;">
                                <span style="display:inline-flex; justify-content:center; align-items:center; width:28px; height:28px; border-radius:50%; background:${viz.color}; color:#0b0d14; font-size:0.85rem; font-weight:700;">${viz.icon}</span>
                                ${p.soil}
                            </span>
                        </div>
                        <div class="forecast-details">
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
                dot.className = 'forecast-dot ' + (idx === 0 ? 'forecast-dot-active' : 'forecast-dot-inactive');
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
                    dots[i].className = 'forecast-dot ' + (i === active ? 'forecast-dot-active' : 'forecast-dot-inactive');
                }
            });

            if (bestOverall) {
                bestEl.innerHTML = `⭐ Лучшее время старта: <strong>${bestOverall.dayLabel}, ${bestOverall.label}</strong> — ${bestOverall.soil}, +${bestOverall.temp}°C, ветер ${bestOverall.wind} м/с`;
                bestEl.className = 'best-time';
            }
            if (window.umami) umami.track('forecast_view', { park_id: parkId, days_count: data.forecast.length });
        } catch (e) {
            console.error('Ошибка прогноза:', e);
        }
    })();

    loadPhotos();

    function updateCharts() {
        var ct = chartTheme();
        if (tempChart) {
            tempChart.options.scales.x.ticks.color = ct.tick;
            tempChart.options.scales.y.ticks.color = ct.tick;
            tempChart.options.scales.x.grid.color = ct.grid;
            tempChart.options.scales.y.grid.color = ct.grid;
            tempChart.options.plugins.datalabels.color = ct.text;
            tempChart.update();
        }
        if (rainChart) {
            rainChart.options.scales.x.ticks.color = ct.tick;
            rainChart.options.scales.y.ticks.color = ct.tick;
            rainChart.options.scales.x.grid.color = ct.grid;
            rainChart.options.scales.y.grid.color = ct.grid;
            rainChart.options.plugins.datalabels.color = ct.accent;
            rainChart.update();
        }
    }

    // theme toggle
    var ptBtn = document.getElementById('parkThemeToggle');
    if (ptBtn) {
        ptBtn.textContent = document.documentElement.classList.contains('theme-light') ? '☀️' : '🌙';
        ptBtn.addEventListener('click', function() {
            document.documentElement.classList.toggle('theme-light');
            var isLight = document.documentElement.classList.contains('theme-light');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            ptBtn.textContent = isLight ? '☀️' : '🌙';
            updateCharts();
        });
    }
})();