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

async function loadUser() {
    if (!token) return;
    try {
        const res = await fetch('/api/user/me', { headers: { 'Authorization': 'Bearer ' + token } });
        if (res.ok) {
            currentUser = await res.json();
            document.getElementById('userInfo').style.display = 'inline';
            document.getElementById('userEmail').textContent = currentUser.email;
            document.getElementById('loginBtn').style.display = 'none';
        } else {
            logout();
        }
    } catch(e) {}
}

function logout() {
    token = '';
    currentUser = null;
    myVotes = {};
    localStorage.removeItem('token');
    document.getElementById('userInfo').style.display = 'none';
    document.getElementById('loginBtn').style.display = 'inline';
    allFavorites = [];
}

// ==================== МОДАЛЬНОЕ ОКНО ====================
var modal = document.getElementById('authModal');
var closeModal = document.querySelector('.close-modal');
var isRegister = false;

document.getElementById('loginBtn').onclick = () => { modal.classList.remove('hidden'); };
closeModal.onclick = () => { modal.classList.add('hidden'); };

document.getElementById('toggleMode').onclick = function(e) {
    e.preventDefault();
    isRegister = !isRegister;
    document.getElementById('modalTitle').textContent = isRegister ? 'Регистрация' : 'Вход';
    document.getElementById('authSubmitBtn').textContent = isRegister ? 'Зарегистрироваться' : 'Войти';
    document.getElementById('authToggle').innerHTML = isRegister
        ? 'Уже есть аккаунт? <a href="#" id="toggleMode">Войти</a>'
        : 'Нет аккаунта? <a href="#" id="toggleMode">Зарегистрироваться</a>';
    document.getElementById('toggleMode').onclick = arguments.callee;
};

document.getElementById('authForm').onsubmit = async function(e) {
    e.preventDefault();
    const email = document.getElementById('authEmail').value;
    const password = document.getElementById('authPassword').value;
    const url = isRegister ? '/api/auth/register' : '/api/auth/login';
    const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password})
    });
    const data = await res.json();
    if (data.ok) {
        if (!isRegister) {
            token = data.token;
            localStorage.setItem('token', token);
            await loadUser();
        } else {
            alert('Регистрация успешна! Теперь войдите.');
            isRegister = false;
            document.getElementById('modalTitle').textContent = 'Вход';
            document.getElementById('authSubmitBtn').textContent = 'Войти';
            document.getElementById('authToggle').innerHTML = 'Нет аккаунта? <a href="#" id="toggleMode">Зарегистрироваться</a>';
            document.getElementById('toggleMode').onclick = arguments.callee;
        }
        modal.classList.add('hidden');
        document.getElementById('authError').textContent = '';
        loadAll();
    } else {
        document.getElementById('authError').textContent = data.detail || 'Ошибка';
    }
};

document.getElementById('logoutBtn').onclick = function() { logout(); loadAll(); };

// ==================== ФОРМАТИРОВАНИЕ ДАТ ====================
var DAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
var MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
function formatDay(date) { return DAYS[date.getDay()] + ' ' + date.getDate() + ' ' + MONTHS[date.getMonth()]; }
function isToday(date) { var today = new Date(); return date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear(); }

// ==================== ФУНКЦИИ ТАЙМЕРА ====================
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
    avgVote: null,   // средняя оценка
    voteCount: 0,    // количество голосов
    myVote: null     // голос текущего пользователя
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
var allFavorites = [];

async function loadFavorites() {
    if (!currentUser) return;
    const res = await fetch('/api/user/favorites', { headers: { 'Authorization': 'Bearer ' + token } });
    if (res.ok) {
        allFavorites = (await res.json()).map(f => f.id);
    }
}

async function loadAllGroupsFiltered() {
    var allGroups = ['mtb_parks', 'mtb_mountains', 'pamps'];
    var allResults = [];
    for (var g of allGroups) {
        let resp = await fetch('/api/weather/' + g);
        if (resp.ok) {
            let data = await resp.json();
            allResults = allResults.concat(data);
        }
    }
    var filtered = allResults.filter(r => allFavorites.includes(r.park.id));
    var parkDataArray = filtered.map(processWeatherData);
    // загрузим голосование для избранного
    await enrichWithVotes(parkDataArray);
    renderAll(parkDataArray);
}

async function enrichWithVotes(parkDataArray) {
    // загружаем агрегированные голоса для всех парков
    const votesRes = await fetch('/api/votes');
    if (votesRes.ok) {
        var allVotes = await votesRes.json();
        for (var p of parkDataArray) {
            p.avgVote = allVotes[p.parkId]?.avg || null;
            p.voteCount = allVotes[p.parkId]?.count || 0;
        }
    }
    if (currentUser) {
        const myRes = await fetch('/api/vote/my', { headers: { 'Authorization': 'Bearer ' + token } });
        if (myRes.ok) {
            myVotes = await myRes.json();
            for (var p of parkDataArray) {
                p.myVote = myVotes[p.parkId] || null;
            }
        }
    }
}

function loadAll() {
  var dashboard = document.getElementById('dashboard');
  dashboard.innerHTML = '<div class="loading">⏳ Загрузка данных...</div>';

  if (currentGroup === 'favorites') {
      if (!currentUser) {
          dashboard.innerHTML = '<div class="loading">Войдите, чтобы увидеть избранные парки</div>';
          return;
      }
      loadFavorites().then(() => {
          if (allFavorites.length === 0) {
              dashboard.innerHTML = '<div class="loading">У вас нет избранных парков</div>';
              return;
          }
          loadAllGroupsFiltered();
      });
      return;
  }

  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/api/weather/' + currentGroup, true);
  xhr.timeout = 15000;
  xhr.onload = async function() {
    if (xhr.status === 200) {
      var results = JSON.parse(xhr.responseText);
      var parkDataArray = results.map(processWeatherData);
      await enrichWithVotes(parkDataArray);
      renderAll(parkDataArray);
    } else {
      dashboard.innerHTML = '<div class="loading">⚠️ Ошибка сервера</div>';
    }
  };
  xhr.onerror = function() { dashboard.innerHTML = '<div class="loading">⚠️ Нет соединения</div>'; };
  xhr.send();
}

// ==================== РЕНДЕРИНГ ====================
function renderAll(parkDataArray) {
  var dashboard = document.getElementById('dashboard');
  var html = '';
  for (var i = 0; i < parkDataArray.length; i++) {
    var park = parkDataArray[i];
    var isFav = allFavorites.includes(park.parkId);
    html += '<div class="card">';
    html += '<div class="park-title">' + park.name + ' <span class="coords">' + park.lat.toFixed(4) + ', ' + park.lon.toFixed(4) + '</span>';
    if (currentUser) {
       html += '<span class="fav-icon' + (isFav ? ' active' : '') + '" data-park-id="' + park.parkId + '">' + (isFav ? '♥' : '♡') + '</span>';
    }
    html += '</div>';

    html += '<div class="current-weather"><span class="weather-emoji">' + getEmoji(park.currentCode) + '</span>';
    html += '<span><span class="temp-value">' + (park.currentTemp !== null ? park.currentTemp : '--') + '</span><span class="temp-degree">°C</span></span></div>';

    html += '<div class="timer-section"><div class="soil-status-badge">' + park.soilStatus + '</div>';
    var rem = park.dryTarget ? (park.dryTarget - Date.now()) : 0;
    var timerResult = formatTimerText(rem > 0 ? rem : 0);
    if (!timerResult.ready) html += '<div class="timer-display">' + timerResult.text + '</div>';
    html += '<div class="rain-amount ' + (park.rain_total > 0.5 ? 'wet' : 'dry') + '">Осадки за 7 д: ' + park.rain_total.toFixed(1) + ' мм</div>';
    html += '</div>';

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

    // Виджет голосования
    html += '<div class="vote-widget">';
    if (park.avgVote !== null) {
        html += '<div class="vote-result">Оценка: ' + park.avgVote.toFixed(1) + ' (' + getVoteLabel(Math.round(park.avgVote)) + '), голосов: ' + park.voteCount + '</div>';
        html += '<div class="avg-bar"><div class="avg-fill" style="width:' + ((park.avgVote-1)/4*100) + '%"></div></div>';
    } else {
        html += '<div class="vote-result">Пока нет голосов</div>';
    }
    if (currentUser) {
        html += '<div class="vote-options">';
        var labels = ['🌿', '💧', '🌵', '✅', '🪨'];
        var titles = ['Болото', 'Мокро', 'Альденте', 'Сухо', 'Бетон'];
        for (var v = 1; v <= 5; v++) {
            html += '<div class="vote-option' + (park.myVote === v ? ' selected' : '') + '" data-vote="' + v + '" data-park-id="' + park.parkId + '">';
            html += '<span class="vote-emoji">' + labels[v-1] + '</span>';
            html += '<span>' + titles[v-1] + '</span>';
            html += '</div>';
        }
        html += '</div>';
    }
    html += '</div>';

    html += '</div>'; // card
  }
  dashboard.innerHTML = html;
  window._parkData = parkDataArray;
  startLiveTimers();
  attachFavListeners();
  attachVoteListeners();
}

function attachVoteListeners() {
    if (!currentUser) return;
    document.querySelectorAll('.vote-option').forEach(option => {
        option.addEventListener('click', async function() {
            const parkId = this.dataset.parkId;
            const vote = parseInt(this.dataset.vote);
            const card = this.closest('.card');
            card.querySelectorAll('.vote-option').forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');
            const res = await fetch('/api/vote/' + parkId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                body: JSON.stringify({ vote: vote })
            });
            if (res.ok) {
                const data = await res.json();
                myVotes[parkId] = vote;
                const resultDiv = card.querySelector('.vote-result');
                if (resultDiv) {
                    resultDiv.textContent = 'Оценка: ' + data.new_avg.toFixed(1) + ' (' + getVoteLabel(Math.round(data.new_avg)) + '), голосов: ' + data.vote_count;
                }
                const fillBar = card.querySelector('.avg-fill');
                if (fillBar) {
                    fillBar.style.width = ((data.new_avg - 1) / 4 * 100) + '%';
                }
            }
        });
    });
}

function attachFavListeners() {
    if (!currentUser) return;
    document.querySelectorAll('.fav-icon').forEach(el => {
        el.onclick = async function() {
            var parkId = this.dataset.parkId;
            var isFav = allFavorites.includes(parkId);
            var method = isFav ? 'DELETE' : 'POST';
            var res = await fetch('/api/user/favorites/' + parkId, {
                method: method,
                headers: { 'Authorization': 'Bearer ' + token }
            });
            if (res.ok) {
                if (isFav) {
    allFavorites = allFavorites.filter(id => id !== parkId);
    this.classList.remove('active');
    this.textContent = '♡';
} else {
    allFavorites.push(parkId);
    this.classList.add('active');
    this.textContent = '♥';
}
                if (currentGroup === 'favorites') loadAll();
            }
        };
    });
}

// ==================== ЖИВЫЕ ТАЙМЕРЫ ====================
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
    document.querySelectorAll('.group-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentGroup = btn.getAttribute('data-group');
    loadAll();
  });
});

document.getElementById('refreshBtn').addEventListener('click', loadAll);

// Старт
loadUser().then(() => loadAll());
setInterval(loadAll, 10 * 60 * 1000);