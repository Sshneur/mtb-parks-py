// ==================== ИКОНКИ ПОГОДЫ ====================
var weatherEmoji = {
  0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
  45: '🌫️', 48: '🌫️',
  51: '🌦️', 53: '🌦️', 55: '🌦️',
  61: '🌧️', 63: '🌧️', 65: '🌧️',
  71: '🌨️', 73: '🌨️', 75: '🌨️',
  80: '🌦️', 81: '🌦️', 82: '🌦️',
  95: '⛈️', 96: '⛈️', 99: '⛈️'
};
function getEmoji(code) { return weatherEmoji[code] || '🌡️'; }

// ==================== АВТОРИЗАЦИЯ ====================
var token = localStorage.getItem('token') || '';
var currentUser = null;
var myVotes = {};

var oauthConsumePromise = null;
(function extractOAuthCode() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('ocode');
    if (!code) return;
    oauthConsumePromise = (async function() {
        try {
            const res = await fetch('/api/auth/oauth/consume', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code})
            });
            const data = await res.json();
            if (!res.ok || !data.token) {
                window.location.href = '/login?error=oauth_consume_failed';
                return;
            }
            token = data.token;
            localStorage.setItem('token', data.token);
            window.history.replaceState({}, '', window.location.pathname);
        } catch(e) {
            window.location.href = '/login?error=oauth_consume_failed';
        }
    })();
})();

async function loadUser() {
    if (!token) return;
    try {
        const res = await fetch('/api/user/me', { headers: { 'Authorization': 'Bearer ' + token } });
        if (res.ok) {
            currentUser = await res.json();
            updateBurgerAuth();
            await updateLevelDisplay();
            refreshToken();
        } else if (res.status === 401) {
            logout();
        }
    } catch(e) {}
}

async function refreshToken() {
    try {
        const res = await fetch('/api/auth/refresh', { headers: { 'Authorization': 'Bearer ' + token } });
        if (res.ok) {
            const data = await res.json();
            if (data.token && data.token !== token) {
                token = data.token;
                localStorage.setItem('token', token);
            }
        }
    } catch(e) {}
}

function logout() {
    token = '';
    currentUser = null;
    myVotes = {};
    localStorage.removeItem('token');
    updateBurgerAuth();
    document.getElementById('levelMobile').style.display = 'none';
}

// ==================== FAB (ПЛАВАЮЩАЯ КНОПКА) ====================
const fabBtn = document.getElementById('fabBtn');
const fabMenu = document.getElementById('fabMenu');
const fabOverlay = document.getElementById('fabOverlay');

function closeFabMenu() {
    fabMenu.classList.remove('open');
    fabOverlay.classList.remove('open');
}

if (fabBtn && fabMenu && fabOverlay) {
    fabBtn.addEventListener('click', function() {
        if (fabMenu.classList.contains('open')) {
            closeFabMenu();
            if (window.umami) umami.track('fab_menu_close');
        } else {
            fabMenu.classList.add('open');
            fabOverlay.classList.add('open');
            if (window.umami) umami.track('fab_menu_open');
        }
    });
    fabOverlay.addEventListener('click', function() {
        closeFabMenu();
        if (window.umami) umami.track('fab_menu_close');
    });

    // Скрытие при скролле вниз / показ при скролле вверх
    var lastScrollY = window.scrollY;
    var ticking = false;

    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(function() {
                var currentScrollY = window.scrollY;
                if (currentScrollY > lastScrollY && currentScrollY > 80) {
                    fabBtn.classList.add('hidden');
                } else {
                    fabBtn.classList.remove('hidden');
                }
                lastScrollY = currentScrollY;
                ticking = false;
            });
            ticking = true;
        }
    });
}

function updateBurgerAuth() {
    const userInfoMobile = document.getElementById('userInfoMobile');
    const userEmailMobile = document.getElementById('userEmailMobile');
    const logoutMobile = document.getElementById('logoutMobile');
    const loginMobile = document.getElementById('loginMobile');

    if (currentUser) {
        userInfoMobile.style.display = 'block';
        userEmailMobile.textContent = currentUser.username || currentUser.email;
        logoutMobile.style.display = 'block';
        loginMobile.style.display = 'none';
    } else {
        userInfoMobile.style.display = 'none';
        logoutMobile.style.display = 'none';
        loginMobile.style.display = 'block';
    }
}

var logoutBtnMobile = document.getElementById('logoutBtnMobile');
if (logoutBtnMobile) {
    logoutBtnMobile.addEventListener('click', function() {
        if (window.umami) umami.track('logout');
        logout();
        loadAll();
        closeFabMenu();
    });
}

// ==================== ОБНОВЛЕНИЕ УРОВНЯ ====================
async function updateLevelDisplay() {
    const levelMobile = document.getElementById('levelMobile');
    const levelDisplay = document.getElementById('levelDisplay');
    if (!levelMobile || !levelDisplay) return;

    if (!currentUser) {
        levelMobile.style.display = 'none';
        return;
    }

    try {
        const res = await fetch('/api/user/stats', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        if (res.ok) {
            const data = await res.json();
            levelDisplay.textContent = `🎯 Уровень: ${data.level} (оценок: ${data.photo_votes_count})`;
            levelMobile.style.display = 'block';
        } else {
            levelMobile.style.display = 'none';
        }
    } catch (e) {
        levelMobile.style.display = 'none';
    }
}

// ==================== ФОРМАТИРОВАНИЕ ДАТ ====================
var DAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
var MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
function formatDay(date) { return DAYS[date.getDay()] + ' ' + date.getDate() + ' ' + MONTHS[date.getMonth()]; }
function isToday(date) { var today = new Date(); return date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear(); }

// ==================== ТАЙМЕР ====================
function formatTimerText(ms) {
  if (ms <= 0) return { text: '', ready: true };
  var sec = Math.floor(ms / 1000);
  var d = Math.floor(sec / 86400);
  var h = Math.floor((sec % 86400) / 3600);
  var m = Math.floor((sec % 3600) / 60);
  var s = sec % 60;
  var pad = function(n) { return n < 10 ? '0' + n : '' + n; };
  var word = d === 1 ? 'день' : d < 5 ? 'дня' : 'дней';
  if (d > 0) return { text: d + ' ' + word + ' ' + pad(h) + ':' + pad(m) + ':' + pad(s), ready: false };
  return { text: pad(h) + ':' + pad(m) + ':' + pad(s), ready: false };
}

// ==================== ОБРАБОТКА ДАННЫХ ====================
function processWeatherData(result) {
  var park = result.park;
  var forecastData = result.forecast;
  var data = {
    name: park.name,
    lat: park.lat,
    lon: park.lon,
    soilStatus: park.soilStatus || 'Нет данных',
    dryTarget: park.dryTarget || null,
    rain_total: park.rain_total || 0,
    currentTemp: null,
    currentCode: null,
    hourly: [],
    daily: [],
    parkId: park.id,
    avgVote: null,
    voteCount: 0,
    rainReset: false
  };

  if (!forecastData) return data;

  var hourly = forecastData.hourly || {};
  var hTimes = hourly.time || [], hTemps = hourly.temperature_2m || [], hCodes = hourly.weather_code || [], hRains = hourly.rain || [];
  data.hourly = [];
  for (var i = 0; i < Math.min(6, hTimes.length); i++) {
    data.hourly.push({
      time: new Date(hTimes[i]).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' }),
      temp: Math.round(hTemps[i] || 0),
      code: hCodes[i],
      rain: hRains[i] || 0,
      isNow: i === 0
    });
  }
  if (data.hourly.length > 0) {
    data.currentTemp = data.hourly[0].temp;
    data.currentCode = data.hourly[0].code;
  }

  var daily = forecastData.daily || {};
  var dTimes = daily.time || [], dMax = daily.temperature_2m_max || [], dRain = daily.rain_sum || [], dCodes = daily.weather_code || [];
  data.daily = [];
  var today = new Date(); today.setHours(0,0,0,0);
  for (var i = 0; i < dTimes.length; i++) {
    var date = new Date(dTimes[i]);
    if (date >= today) {
      data.daily.push({ date: date, temp: Math.round(dMax[i] || 0), rain: dRain[i] || 0, code: dCodes[i] || null, isToday: isToday(date) });
    }
  }
  return data;
}

function getVoteLabel(vote) {
  const labels = {1: 'Болото', 2: 'Мокро', 3: 'Альденте', 4: 'Сухо', 5: 'Бетон'};
  return labels[vote] || '';
}

// ==================== ЗАГРУЗКА ДАННЫХ ====================
var currentGroup = 'mtb_parks';
var currentModel = 'standard';

var catalogData = null;
var startParkIds = [];
var startConfigured = false;

function readGuestStartParks() {
    try {
        var v = localStorage.getItem('startParks');
        if (!v) return null;
        var arr = JSON.parse(v);
        return Array.isArray(arr) ? arr.filter(Boolean) : null;
    } catch(e) { return null; }
}

function getDefaultStartIds() {
    var fallback = ['fili', 'erino', 'chess', 'kozlovka'];
    if (!catalogData) return fallback;
    var ids = [];
    for (var i = 0; i < catalogData.length; i++) {
        if (catalogData[i].group_id === 'mtb_parks') ids.push(catalogData[i].parkId);
        if (ids.length >= 4) break;
    }
    return ids.length ? ids : fallback;
}

async function loadCatalog() {
    if (catalogData) return catalogData;
    try {
        var res = await fetch('/api/parks/catalog');
        if (res.ok) {
            catalogData = await res.json();
            return catalogData;
        }
    } catch(e) {}
    return null;
}

function activateGroup(group) {
    document.querySelectorAll('.group-btn').forEach(b => b.classList.remove('active'));
    var btn = document.querySelector('.group-btn[data-group="' + group + '"]');
    if (btn) btn.classList.add('active');
    currentGroup = group;
}

async function loadStartPage() {
    var dashboard = document.getElementById('dashboard');
    dashboard.innerHTML = '<div class="loading">⏳ Загрузка данных...</div>';
    catalogData = await loadCatalog();
    try {
        if (currentUser) {
            var res = await fetch('/api/user/start-parks', { headers: { 'Authorization': 'Bearer ' + token } });
            if (res.ok) {
                var data = await res.json();
                startConfigured = data.configured;
                startParkIds = data.parks.map(function(p) { return p.park_id; });
                if (!startConfigured) {
                    var guest = readGuestStartParks();
                    if (guest && guest.length) {
                        var sv = await fetch('/api/user/start-parks', {
                            method: 'POST',
                            headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
                            body: JSON.stringify({ park_ids: guest })
                        });
                        if (sv.ok) {
                            startConfigured = true;
                            startParkIds = guest;
                            localStorage.removeItem('startParks');
                        }
                    }
                }
            }
        } else {
            var guest = readGuestStartParks();
            startConfigured = false;
            startParkIds = guest && guest.length ? guest : getDefaultStartIds();
        }
    } catch(e) {
        startConfigured = false;
        startParkIds = readGuestStartParks() || getDefaultStartIds();
    }

    if (!startParkIds.length) {
        dashboard.innerHTML = '<div class="empty-state">Здесь пока нет парков.<br>' +
            '<button class="catalog-link-btn" onclick="openCatalog()">Выбрать из каталога</button></div>';
        return;
    }

    var hint = '';
    if (currentUser) {
        hint = '<div class="start-hint">' +
            (startConfigured
                ? '📌 Ваша стартовая страница: ' + startParkIds.length + ' парк(ов). '
                : '⭐ Страница по умолчанию. Настройте её под себя: ') +
            '<button class="catalog-link-btn" onclick="openCatalog()">Настроить</button></div>';
    } else {
        hint = '<div class="start-hint">Отметьте парки в каталоге — они появятся здесь. ' +
            '<button class="catalog-link-btn" onclick="openCatalog()">Выбрать парки</button></div>';
    }

    await loadWeatherForIds(startParkIds, hint);
}

async function loadWeatherForIds(ids, prehtml) {
    var allGroups = ['mtb_parks', 'mtb_mountains', 'pamps'];
    var byId = {};
    for (var g of allGroups) {
        var url = currentModel === 'pm' ? '/api/weather/pm/' + g : '/api/weather/' + g;
        try {
            var resp = await fetch(url);
            if (resp.ok) {
                var arr = await resp.json();
                if (Array.isArray(arr)) {
                    for (var it of arr) {
                        if (it && it.park) byId[it.park.id] = it;
                    }
                }
            }
        } catch(e) {}
    }
    var results = [];
    for (var i = 0; i < ids.length; i++) {
        if (byId[ids[i]]) results.push(byId[ids[i]]);
    }
    var parkDataArray = results.map(processWeatherData);
    await enrichWithVotes(parkDataArray);
    renderAll(parkDataArray, prehtml);
}

async function enrichWithVotes(parkDataArray) {
    const votesRes = await fetch('/api/votes');
    if (votesRes.ok) {
        var allVotes = await votesRes.json();
        for (var p of parkDataArray) {
            p.avgVote = allVotes[p.parkId]?.avg ?? null;
            p.voteCount = allVotes[p.parkId]?.count ?? 0;
            p.rainReset = allVotes[p.parkId]?.rain_reset ?? false;
        }
    }
}

function loadAll() {
  var dashboard = document.getElementById('dashboard');
  dashboard.innerHTML = '<div class="loading">⏳ Загрузка данных...</div>';

  if (currentGroup === 'mtb_parks') {
      loadStartPage();
      return;
  }

  var url = currentModel === 'pm' ? '/api/weather/pm/' + currentGroup : '/api/weather/' + currentGroup;
  var xhr = new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.timeout = 15000;
  xhr.onload = async function() {
    if (xhr.status === 200) {
      try {
        var results = JSON.parse(xhr.responseText);
        if (!Array.isArray(results)) results = [];
        var parkDataArray = results.map(processWeatherData);
        await enrichWithVotes(parkDataArray);
        renderAll(parkDataArray);
      } catch (e) {
        dashboard.innerHTML = '<div class="loading">⚠️ Ошибка обработки данных</div>';
      }
    } else {
      dashboard.innerHTML = '<div class="loading">⚠️ Ошибка сервера: ' + xhr.status + '</div>';
    }
  };
  xhr.onerror = function() { dashboard.innerHTML = '<div class="loading">⚠️ Нет соединения</div>'; };
  xhr.send();
}

// ==================== РЕНДЕРИНГ ====================
function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderAll(parkDataArray, prehtml) {
  var dashboard = document.getElementById('dashboard');
  var html = '';
  for (var i = 0; i < parkDataArray.length; i++) {
    var park = parkDataArray[i];
    html += '<div class="card" data-park-id="' + escapeHtml(park.parkId) + '">';
    html += '<div class="park-title"><a href="/park/' + escapeHtml(park.parkId) + '" style="color:inherit; text-decoration:none;">' + escapeHtml(park.name) + '</a> <span class="coords">' + park.lat.toFixed(4) + ', ' + park.lon.toFixed(4) + '</span></div>';

    html += '<div class="current-weather"><span class="weather-emoji">' + getEmoji(park.currentCode) + '</span>';
    html += '<span><span class="temp-value">' + (park.currentTemp !== null ? park.currentTemp : '--') + '</span><span class="temp-degree">°C</span></span></div>';

    html += '<div class="timer-section"><div class="soil-status-badge">' + park.soilStatus + '</div>';
    var rem = park.dryTarget ? (park.dryTarget - Date.now()) : 0;
    var timerResult = formatTimerText(rem > 0 ? rem : 0);
    if (!timerResult.ready) html += '<div class="timer-display">' + timerResult.text + '</div>';
    html += '<div class="rain-amount ' + (park.rain_total > 0.5 ? 'wet' : 'dry') + '">Осадки за 7 д: ' + park.rain_total.toFixed(1) + ' мм</div>';
    html += '</div>';

    // Прогноз на 6 часов (перенесён выше графика осадков)
    html += '<div class="hourly-strip"><div class="section-title">Прогноз на 6 часов</div><div class="hourly-row">';
    for (var j = 0; j < park.hourly.length; j++) {
      var s = park.hourly[j];
      html += '<div class="hourly-cell' + (s.isNow ? ' now-cell' : '') + '">';
      html += '<div class="hour-time">' + (s.isNow ? '<span class="now-badge">СЕЙЧАС</span>' : s.time.slice(0,5)) + '</div>';
      html += '<div class="hour-emoji">' + getEmoji(s.code) + '</div>';
      html += '<div class="hour-temp">' + (s.temp !== null ? s.temp + '°' : '--') + '</div>';
      html += '<div class="hour-rain">' + (s.rain > 0 ? s.rain.toFixed(1) + 'мм' : '0') + '</div>';
      html += '</div>';
    }
    html += '</div></div>';

    // График осадков (теперь после прогноза)
    if (park.hourly.length > 0) {
      html += '<div class="rain-graph"><div class="section-title">Осадки (мм/час)</div><div class="rain-bars">';
      var maxRain = 0.1;
      for (var j = 0; j < park.hourly.length; j++) {
        if (park.hourly[j].rain > maxRain) maxRain = park.hourly[j].rain;
      }
      for (var j = 0; j < park.hourly.length; j++) {
        var s = park.hourly[j];
        html += '<div class="rain-bar-wrapper"><div class="rain-bar' + (s.isNow ? ' now' : '') + '" style="height:' + Math.max((s.rain / maxRain) * 100, 5) + '%"></div><div class="rain-value">' + s.rain.toFixed(1) + '</div></div>';
      }
      html += '</div></div>';
    }

    // Дневной прогноз
    html += '<div class="daily-table"><div class="section-title">Прогноз на 6 дней</div>';
    for (var j = 0; j < park.daily.length; j++) {
      var d = park.daily[j];
      html += '<div class="daily-row' + (d.isToday ? ' today' : '') + '">';
      html += '<span class="daily-day">' + (d.isToday ? 'СЕГОДНЯ' : formatDay(d.date)) + '</span>';
      html += '<span class="daily-icon">' + getEmoji(d.code) + '</span>';
      html += '<span class="daily-temp">' + d.temp + '°</span>';
      html += '<span class="daily-rain">' + (d.rain > 0 ? d.rain.toFixed(1) + 'мм' : '0') + '</span>';
      html += '</div>';
    }
    html += '</div>';

    // Виджет оценок (с учётом rainReset)
    html += '<div class="vote-widget">';
    if (park.avgVote !== null && park.avgVote !== undefined) {
        html += '<div class="vote-result">⭐ ' + park.avgVote.toFixed(1) + ' (' + getVoteLabel(Math.round(park.avgVote)) + '), голосов: ' + park.voteCount + '</div>';
        html += '<div class="avg-bar"><div class="avg-fill" style="width:' + ((park.avgVote-1)/4*100) + '%"></div></div>';
    } else if (park.rainReset) {
        html += '<div class="vote-result" style="color:#ff6b6b;">🌧️ Оценки сброшены после дождя. Загрузите новое фото!</div>';
    } else {
        html += '<div class="vote-result">Пока нет оценок</div>';
    }
    html += '</div>';

    html += '</div>'; // card
  }
  if (prehtml) html += prehtml;
  dashboard.innerHTML = html;

  // ===== КЛИК ПО КАРТОЧКЕ (кроме интерактивных элементов) =====
  document.querySelectorAll('.card').forEach(card => {
      card.addEventListener('click', function(e) {
          if (e.target.closest('a') || e.target.closest('button')) {
              return;
          }
          const parkId = this.dataset.parkId;
          if (parkId) {
              if (window.umami) umami.track('park_view', { park_id: parkId, group: currentGroup, model: currentModel });
              window.location.href = '/park/' + parkId;
          }
      });
      card.style.cursor = 'pointer';
  });

  window._parkData = parkDataArray;
  startLiveTimers();
}

// ==================== ТАЙМЕРЫ ====================
var timerInterval;
function startLiveTimers() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(function() {
    if (!window._parkData) return;
    var cards = document.querySelectorAll('.card');
    for (var i = 0; i < cards.length; i++) {
      var parkName = cards[i].querySelector('.park-title')?.textContent;
      if (!parkName) continue;
      var park = null;
      for (var j = 0; j < window._parkData.length; j++) {
        if (parkName.indexOf(window._parkData[j].name) >= 0) { park = window._parkData[j]; break; }
      }
      if (!park || !park.dryTarget) continue;
      var display = cards[i].querySelector('.timer-display');
      if (!display) continue;
      var rem = park.dryTarget - Date.now();
      var timerResult = formatTimerText(rem > 0 ? rem : 0);
      if (!timerResult.ready) display.textContent = timerResult.text;
    }
  }, 1000);
}

// ==================== ЧАСЫ ====================
function updateClock() {
  var el = document.getElementById('liveDateTime');
  if (!el) return;
  var now = new Date();
  el.textContent = now.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'Europe/Moscow' });
}
setInterval(updateClock, 1000);
updateClock();

// ==================== ГРУППЫ ====================
document.querySelectorAll('.group-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var group = btn.getAttribute('data-group');
    if (group === 'all_parks') {
        openCatalog();
        return;
    }
    document.querySelectorAll('.group-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentGroup = group;
    if (window.umami) umami.track('group_switch', { group: currentGroup });
    loadAll();
  });
});

// ==================== МОДЕЛИ ====================
currentModel = localStorage.getItem('model') === 'pm' ? 'pm' : 'standard';
var modelToggle = document.getElementById('modelToggle');
if (modelToggle) {
    modelToggle.checked = currentModel === 'pm';
    modelToggle.addEventListener('change', function() {
        currentModel = modelToggle.checked ? 'pm' : 'standard';
        localStorage.setItem('model', currentModel);
        if (window.umami) umami.track('model_toggle', { model: currentModel });
        loadAll();
    });
}

document.getElementById('refreshBtn').addEventListener('click', function() {
    if (window.umami) umami.track('refresh_data');
    loadAll();
});

// ==================== КАТАЛОГ ПАРКОВ + «ПРЕДЛОЖИ СВОЙ ПАРК» ====================
function selectedStartParkIds() {
    if (startParkIds.length) return startParkIds.slice();
    return readGuestStartParks() || getDefaultStartIds();
}

function renderCatalog() {
    if (!catalogData) return;
    var selIds = {};
    selectedStartParkIds().forEach(function(id) { selIds[id] = true; });
    var panel = document.getElementById('catalogPanel');
    var html = '';
    var lastGroup = '';
    for (var i = 0; i < catalogData.length; i++) {
        var p = catalogData[i];
        if (p.group_name !== lastGroup) {
            lastGroup = p.group_name;
            html += '<div class="catalog-group-title">' + escapeHtml(p.group_name) + '</div>';
        }
        html += '<label class="catalog-item">' +
            '<input type="checkbox" class="catalog-check" value="' + escapeHtml(p.parkId) + '"' + (selIds[p.parkId] ? ' checked' : '') + '>' +
            '<span class="catalog-item-name">' + escapeHtml(p.name) + '</span>' +
            '<span class="catalog-item-status catalog-status-' + (p.soilStatus || 'нет').replace(/[^a-zа-яёА-ЯЁ0-9]/gi, '').toLowerCase() + '">' + escapeHtml(p.soilStatus) + '</span>' +
            '</label>';
    }
    panel.innerHTML = html;
    updateCatalogCount();
}

function updateCatalogCount() {
    var n = document.querySelectorAll('#catalogPanel .catalog-check:checked').length;
    var el = document.getElementById('catalogCount');
    if (el) el.textContent = 'Выбрано: ' + n;
}

async function openCatalog() {
    catalogData = await loadCatalog();
    if (!catalogData) { alert('Не удалось загрузить каталог'); return; }
    document.getElementById('catalogPanel').style.display = 'block';
    document.getElementById('catalogFormPanel').style.display = 'none';
    document.getElementById('catalogTitle').textContent = 'Каталог парков';
    document.getElementById('catalogToggleForm').textContent = '📝 Предложить свой парк';
    document.getElementById('catalogModal').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    renderCatalog();
    if (window.umami) umami.track('catalog_open');
}

function closeCatalog() {
    document.getElementById('catalogModal').style.display = 'none';
    document.body.style.overflow = '';
}

var catalogClose = document.getElementById('catalogClose');
if (catalogClose) catalogClose.addEventListener('click', closeCatalog);

document.getElementById('catalogModal').addEventListener('click', function(e) {
    if (e.target === this) closeCatalog();
});

document.getElementById('catalogPanel').addEventListener('change', function(e) {
    if (e.target.classList.contains('catalog-check')) updateCatalogCount();
});

var catalogToggleForm = document.getElementById('catalogToggleForm');
if (catalogToggleForm) {
    catalogToggleForm.addEventListener('click', function() {
        var panel = document.getElementById('catalogPanel');
        var form = document.getElementById('catalogFormPanel');
        var showing = form.style.display !== 'none';
        form.style.display = showing ? 'none' : 'block';
        panel.style.display = showing ? 'block' : 'none';
        document.getElementById('catalogTitle').textContent = showing ? 'Каталог парков' : '📝 Предложи свой парк';
        catalogToggleForm.textContent = showing ? '📝 Предложи свой парк' : '← К каталогу';
    });
}

document.getElementById('catalogSave').addEventListener('click', async function() {
    var ids = [];
    document.querySelectorAll('#catalogPanel .catalog-check:checked').forEach(function(c) { ids.push(c.value); });
    if (currentUser) {
        var res;
        try {
            res = await fetch('/api/user/start-parks', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
                body: JSON.stringify({ park_ids: ids })
            });
        } catch(e) {
            alert('Ошибка сети');
            return;
        }
        if (res.ok) {
            startConfigured = true;
            startParkIds = ids;
            closeCatalog();
            activateGroup('mtb_parks');
            if (window.umami) umami.track('start_parks_saved', { count: ids.length });
            loadAll();
        } else {
            var d = await res.json().catch(function() { return {}; });
            alert('Ошибка: ' + (d.detail || 'не удалось сохранить'));
        }
    } else {
        localStorage.setItem('startParks', JSON.stringify(ids));
        startParkIds = ids;
        closeCatalog();
        activateGroup('mtb_parks');
        if (window.umami) umami.track('start_parks_guest_saved', { count: ids.length });
        loadAll();
    }
});

document.getElementById('parkRequestForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    var name = document.getElementById('prName').value.trim();
    var lat = parseFloat(document.getElementById('prLat').value);
    var lon = parseFloat(document.getElementById('prLon').value);
    if (!name || isNaN(lat) || isNaN(lon)) return;
    var body = {
        name: name,
        lat: lat,
        lon: lon,
        trails_count: parseInt(document.getElementById('prTrails').value, 10) || 0,
        soil_description: document.getElementById('prSoil').value.trim(),
        description: document.getElementById('prDescription').value.trim(),
        storm_drain: document.getElementById('prStormDrain').value.trim(),
        tg_group: document.getElementById('prTgGroup').value.trim(),
        contact_tg: document.getElementById('prContactTg').value.trim()
    };
    var statusEl = document.getElementById('prStatus');
    statusEl.style.color = 'var(--text-muted)';
    statusEl.textContent = '⏳ Отправка...';
    try {
        var res = await fetch('/api/park/requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        var data = await res.json().catch(function() { return {}; });
        if (res.status === 201) {
            statusEl.style.color = '#4caf50';
            statusEl.textContent = '✅ Заявка отправлена на модерацию!';
            e.target.reset();
            if (window.umami) umami.track('park_request_submit');
        } else if (res.status === 409) {
            statusEl.style.color = '#ff6b6b';
            statusEl.textContent = '⚠️ ' + (data.detail || 'Парк с таким названием уже существует');
        } else {
            statusEl.style.color = '#ff6b6b';
            statusEl.textContent = '⚠️ ' + (data.detail || 'Ошибка отправки заявки');
        }
    } catch(err) {
        statusEl.style.color = '#ff6b6b';
        statusEl.textContent = '⚠️ Ошибка сети';
    }
});

// Старт
(oauthConsumePromise || Promise.resolve()).then(() => loadUser()).then(() => loadAll());
setInterval(loadAll, 10 * 60 * 1000);

// ==================== MINI MAP ====================
(function initMiniMap() {
    var mapEl = document.getElementById('miniMap');
    if (!mapEl || typeof L === 'undefined') return;

    var map = L.map('miniMap', {
        zoomControl: false,
        attributionControl: false,
        scrollWheelZoom: false,
        touchZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
        keyboard: false,
        dragging: true,
        minZoom: 8
    });
    map.setView([55.65, 37.49], 10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18
    }).addTo(map);

    var statusColors = {
        'Бетон': '#ffd700', 'Сухо': '#4caf50', 'Альденте': '#ff9800',
        'Мокро': '#2196f3', 'Болото': '#9c27b0'
    };

    fetch('/api/park/list').then(function(r) { return r.json(); }).then(function(data) {
        if (!data || !data.length) return;
        data.forEach(function(p) {
            var color = '#666';
            for (var key in statusColors) {
                if (p.soilStatus && p.soilStatus.indexOf(key) >= 0) { color = statusColors[key]; break; }
            }
            var marker = L.circleMarker([p.lat, p.lon], {
                radius: 7, color: '#fff', fillColor: color, fillOpacity: 0.9, weight: 2
            }).addTo(map);
            marker.bindPopup(
                '<b><a href="/park/' + p.parkId + '" style="color:#4a90e2;text-decoration:none;">' + p.name + '</a></b><br>' +
                '<span style="font-size:13px;">' + (p.soilStatus || '—') + '</span>'
            );
            marker.on('click', function() {
                if (window.umami) umami.track('mini_map_marker_click', { park_id: p.parkId });
            });
        });
        if (window.umami) umami.track('mini_map_loaded', { park_count: data.length });
    }).catch(function(e) {
        console.error('Mini map error:', e);
    });
})();