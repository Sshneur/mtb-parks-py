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

function getEmoji(code) {
  return weatherEmoji[code] || '🌡️';
}

// ==================== ФОРМАТИРОВАНИЕ ДАТ ====================
var DAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
var MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];

function formatDay(date) {
  return DAYS[date.getDay()] + ' ' + date.getDate() + ' ' + MONTHS[date.getMonth()];
}

function isToday(date) {
  var today = new Date();
  return date.getDate() === today.getDate() &&
         date.getMonth() === today.getMonth() &&
         date.getFullYear() === today.getFullYear();
}

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
  if (d > 0) {
    return { text: d + ' ' + word + ' ' + pad(h) + ':' + pad(m) + ':' + pad(s), ready: false };
  }
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
    dryTarget: park.dryTarget ? new Date(park.dryTarget).getTime() : Date.now(),
    rain_total: park.rain_total || 0,
    currentTemp: null,
    currentCode: null,
    hourly: [],
    daily: []
  };

  if (!forecastData) return data;

  var hourly = forecastData.hourly || {};
  var hTimes = hourly.time || [];
  var hTemps = hourly.temperature_2m || [];
  var hCodes = hourly.weather_code || [];
  var hRains = hourly.rain || [];

  // Собираем почасовые данные
  data.hourly = [];
  for (var i = 0; i < Math.min(6, hTimes.length); i++) {
    data.hourly.push({
      time: new Date(hTimes[i]).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
      temp: Math.round(hTemps[i] || 0),
      code: hCodes[i],
      rain: hRains[i] || 0,
      isNow: i === 0
    });
  }

  // Текущая погода = первый час прогноза (синхронизировано)
  if (data.hourly.length > 0) {
    data.currentTemp = data.hourly[0].temp;
    data.currentCode = data.hourly[0].code;
  }

  // Дневной прогноз
  var daily = forecastData.daily || {};
  var dTimes = daily.time || [];
  var dMax = daily.temperature_2m_max || [];
  var dRain = daily.rain_sum || [];
  var dCodes = daily.weather_code || [];

  data.daily = [];
  var today = new Date();
  today.setHours(0, 0, 0, 0);

  for (var i = 0; i < dTimes.length; i++) {
    var date = new Date(dTimes[i]);
    if (date >= today) {
      data.daily.push({
        date: date,
        temp: Math.round(dMax[i] || 0),
        rain: dRain[i] || 0,
        code: dCodes[i] || null,
        isToday: isToday(date)
      });
    }
  }

  return data;
}

// ==================== ЗАГРУЗКА ДАННЫХ ====================
var currentGroup = 'mtb_parks';

function loadAll() {
  var dashboard = document.getElementById('dashboard');
  dashboard.innerHTML = '<div class="loading">⏳ Загрузка данных...</div>';

  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/api/weather/' + currentGroup, true);
  xhr.timeout = 15000;

  xhr.onload = function() {
    if (xhr.status === 200) {
      try {
        var results = JSON.parse(xhr.responseText);
        var parkDataArray = [];
        for (var i = 0; i < results.length; i++) {
          parkDataArray.push(processWeatherData(results[i]));
        }
        renderAll(parkDataArray);
      } catch (e) {
        dashboard.innerHTML = '<div class="loading">⚠️ Ошибка обработки данных</div>';
      }
    } else {
      dashboard.innerHTML = '<div class="loading">⚠️ Ошибка сервера: ' + xhr.status + '</div>';
    }
  };

  xhr.onerror = function() {
    dashboard.innerHTML = '<div class="loading">⚠️ Нет соединения с сервером</div>';
  };

  xhr.ontimeout = function() {
    dashboard.innerHTML = '<div class="loading">⏰ Превышено время ожидания</div>';
  };

  xhr.send();
}

// ==================== РЕНДЕРИНГ ====================
function renderAll(parkDataArray) {
  var dashboard = document.getElementById('dashboard');
  var html = '';

  for (var i = 0; i < parkDataArray.length; i++) {
    var park = parkDataArray[i];

    html += '<div class="card">';
    html += '<div class="park-title">' + park.name + ' <span class="coords">' + park.lat.toFixed(4) + ', ' + park.lon.toFixed(4) + '</span></div>';

    // Текущая погода (синхронизирована с первым часом)
    html += '<div class="current-weather">';
    html += '<span class="weather-emoji">' + getEmoji(park.currentCode) + '</span>';
    html += '<span><span class="temp-value">' + (park.currentTemp !== null ? park.currentTemp : '--') + '</span><span class="temp-degree">°C</span></span>';
    html += '</div>';

    // Статус грунта
    html += '<div class="timer-section">';
    html += '<div class="soil-status-badge">' + park.soilStatus + '</div>';

    var rem = (park.dryTarget || Date.now()) - Date.now();
    var timerResult = formatTimerText(rem > 0 ? rem : 0);
    if (!timerResult.ready) {
      html += '<div class="timer-display">' + timerResult.text + '</div>';
    }

    html += '<div class="rain-amount ' + (park.rain_total > 0.5 ? 'wet' : 'dry') + '">Осадки за 96ч: ' + park.rain_total.toFixed(1) + ' мм</div>';
    html += '</div>';

    // График осадков
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

    // Почасовой прогноз
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

    html += '</div>';
  }

  dashboard.innerHTML = html;
  window._parkData = parkDataArray;
  startLiveTimers();
}

// ==================== ЖИВЫЕ ТАЙМЕРЫ ====================
var timerInterval;
function startLiveTimers() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(function() {
    if (!window._parkData) return;
    var displays = document.querySelectorAll('.timer-display');
    for (var i = 0; i < window._parkData.length; i++) {
      if (i >= displays.length) continue;
      var park = window._parkData[i];
      var rem = (park.dryTarget || Date.now()) - Date.now();
      var timerResult = formatTimerText(rem > 0 ? rem : 0);
      if (!timerResult.ready) {
        displays[i].textContent = timerResult.text;
      }
    }
  }, 1000);
}

// ==================== ЧАСЫ ====================
function updateClock() {
  var el = document.getElementById('liveDateTime');
  if (!el) return;
  var now = new Date();
  el.textContent = now.toLocaleDateString('ru-RU', {
    day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });
}
setInterval(updateClock, 1000);
updateClock();

// ==================== КНОПКИ ГРУПП ====================
document.querySelectorAll('.group-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('.group-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentGroup = btn.getAttribute('data-group');
    loadAll();
  });
});

// ==================== КНОПКА ОБНОВЛЕНИЯ ====================
document.getElementById('refreshBtn').addEventListener('click', function() {
  loadAll();
});

// ==================== СТАРТ ====================
loadAll();
setInterval(loadAll, 10 * 60 * 1000);