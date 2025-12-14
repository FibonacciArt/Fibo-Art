import requests
import time
import threading
import math
from datetime import datetime, timezone

BOT_TOKEN = "8494428945:AAHzBKk38mXzbFIEGK5mrJ45puRJT9svnEg"
CHAT_ID = "1464388096"
TWELVE_DATA_KEY = "5eba3772052948fca1bc270b9504101a"

settings = {
    "timeframe": "5min",
    "check_interval": 60,
    "volatile_length": 25,      # ТВОИ НАСТРОЙКИ!
    "volatile_mult": 2.1,        # ТВОИ НАСТРОЙКИ!
    "trend_smooth": 52
}

assets_data = {
    "XAUUSD": {
        "name": "Золото",
        "emoji": "🪙",
        "price": 0,
        "volatile": 0,
        "trend": "FLAT",
        "upper": 0,
        "lower": 0,
        "basis": 0,
        "stdev": 0,
        "last_update": 0,
        "last_candle_time": "",
        "candles": [],
        "last_signal_candle": ""
    },
    "BTCUSD": {
        "name": "Bitcoin",
        "emoji": "₿",
        "price": 0,
        "volatile": 0,
        "trend": "FLAT",
        "upper": 0,
        "lower": 0,
        "basis": 0,
        "stdev": 0,
        "last_update": 0,
        "last_candle_time": "",
        "candles": [],
        "last_signal_candle": ""
    }
}

current_asset = "XAUUSD"


def get_btc_candles():
    """Получить свечи Bitcoin от CryptoCompare"""
    try:
        print("   🌐 Запрос BTC свечей...")
        url = "https://min-api.cryptocompare.com/data/v2/histominute"
        params = {
            "fsym": "BTC",
            "tsym": "USD",
            "limit": 100,
            "aggregate": 5
        }
        
        r = requests.get(url, params=params, timeout=15)
        
        if r.status_code != 200:
            print(f"   ❌ HTTP {r.status_code}")
            return None
        
        data = r.json()
        
        if data.get("Response") != "Success":
            print(f"   ❌ API Error: {data}")
            return None
        
        candles_raw = data["Data"]["Data"]
        
        candles = []
        for c in candles_raw:
            candles.append({
                "time": c["time"],
                "datetime": datetime.fromtimestamp(c["time"], tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                "close": float(c["close"])
            })
        
        print(f"   ✅ Получено {len(candles)} свечей BTC")
        print(f"   💰 Последняя цена: ${candles[-1]['close']:,.2f}")
        
        return candles
        
    except Exception as e:
        print(f"   ❌ Ошибка BTC: {e}")
        return None


def get_gold_candles():
    """Получить свечи золота - Twelve Data API"""
    try:
        print("   🌐 Twelve Data API (XAU/USD)...")
        
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": "XAU/USD",
            "interval": "5min",
            "outputsize": 100,
            "apikey": TWELVE_DATA_KEY,
            "format": "JSON"
        }
        
        r = requests.get(url, params=params, timeout=15)
        
        if r.status_code != 200:
            print(f"   ❌ HTTP {r.status_code}")
            return None
        
        data = r.json()
        
        if "values" not in data:
            print(f"   ❌ API Error: {data}")
            return None
        
        if len(data["values"]) == 0:
            print(f"   ❌ Нет данных")
            return None
        
        candles = []
        for c in reversed(data["values"]):
            try:
                dt = datetime.strptime(c["datetime"], '%Y-%m-%d %H:%M:%S')
                candles.append({
                    "time": int(dt.replace(tzinfo=timezone.utc).timestamp()),
                    "datetime": c["datetime"],
                    "close": float(c["close"])
                })
            except:
                continue
        
        if len(candles) > 0:
            print(f"   ✅ Получено {len(candles)} свечей GOLD")
            print(f"   💰 Последняя цена: ${candles[-1]['close']:.2f}")
        
        return candles
        
    except Exception as e:
        print(f"   ❌ Ошибка Twelve Data: {e}")
        return None


def gauss(x, h):
    """Gaussian kernel"""
    return math.exp(-(x ** 2) / (h * h * 2))


def nadaraya_watson(prices, h=52):
    """Nadaraya-Watson Estimator"""
    n = len(prices)
    if n < 10:
        return None
    
    use_n = min(n, h + 10)
    recent_prices = prices[-use_n:]
    n = len(recent_prices)
    
    last_3_points = []
    
    for i in range(n - 3, n):
        sum_val = 0.0
        sumw = 0.0
        
        for j in range(n):
            w = gauss(i - j, h)
            sum_val += recent_prices[j] * w
            sumw += w
        
        last_3_points.append(sum_val / sumw if sumw != 0 else recent_prices[i])
    
    return last_3_points


def bollinger_bands(prices, length=25, mult=2.1, use_population=True):
    """
    Bollinger Bands - ДВЕ ВЕРСИИ
    
    basis = SMA(close, length)
    stdev = stdev(close, length)
    upper = basis + mult * stdev
    lower = basis - mult * stdev
    
    use_population: True = делим на n (population)
                    False = делим на n-1 (sample)
    """
    if len(prices) < length:
        return None, None, None, None
    
    recent = prices[-length:]
    
    # 1. BASIS = Simple Moving Average
    basis = sum(recent) / length
    
    # 2. STDEV - попробуем POPULATION (как в старых версиях Pine Script)
    if use_population:
        # Population StdDev (делим на n)
        variance = sum((x - basis) ** 2 for x in recent) / length
    else:
        # Sample StdDev (делим на n-1)
        variance = sum((x - basis) ** 2 for x in recent) / (length - 1)
    
    stdev = math.sqrt(variance)
    
    # 3. UPPER/LOWER Bands
    upper = basis + stdev * mult
    lower = basis - stdev * mult
    
    return upper, lower, basis, stdev


def bb_percent(price, upper, lower):
    """
    BB %B (Bollinger Bands Percent B)
    
    Формула: (close - lower) / (upper - lower)
    
    Значения:
    - 0.0 (0%) = цена на нижней полосе
    - 0.5 (50%) = цена на средней линии (basis)
    - 1.0 (100%) = цена на верхней полосе
    - < 0 = цена ниже нижней полосы (BUY!)
    - > 1 = цена выше верхней полосы (SELL!)
    """
    if upper == lower:
        return 0.5
    
    bb_pct = (price - lower) / (upper - lower)
    return bb_pct


def send_message(text):
    """Отправить сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=data, timeout=10)
    except:
        pass


def send_keyboard():
    """Клавиатура"""
    keyboard = {
        "keyboard": [
            [{"text": "🪙 Золото"}, {"text": "₿ Bitcoin"}],
            [{"text": "📊 Статус"}],
            [{"text": "💰 Цена"}, {"text": "📈 Индикаторы"}],
            [{"text": "🔄 Обновить"}, {"text": "/all"}],
            [{"text": "🔍 DEBUG BB"}]
        ],
        "resize_keyboard": True
    }
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": "Выбери актив:", "reply_markup": keyboard}
        requests.post(url, json=data, timeout=10)
    except:
        pass


def get_status_text(asset_key):
    """Получить статус актива"""
    d = assets_data[asset_key]
    trend_emoji = "🟢" if d["trend"] == "UP" else "🔴" if d["trend"] == "DOWN" else "⚪"
    
    price_str = f"${d['price']:,.2f}" if asset_key == "BTCUSD" else f"${d['price']:.2f}"
    upper_str = f"${d['upper']:,.2f}" if asset_key == "BTCUSD" else f"${d['upper']:.2f}"
    lower_str = f"${d['lower']:,.2f}" if asset_key == "BTCUSD" else f"${d['lower']:.2f}"
    basis_str = f"${d['basis']:,.2f}" if asset_key == "BTCUSD" else f"${d['basis']:.2f}"
    
    seconds_ago = int(time.time() - d["last_update"])
    if seconds_ago < 60:
        update_text = f"{seconds_ago}с назад"
    elif seconds_ago < 3600:
        update_text = f"{seconds_ago // 60}м назад"
    else:
        update_text = f"{seconds_ago // 3600}ч назад"
    
    # BB %B в процентах
    bb_percent_display = d['volatile'] * 100
    
    return f"""<b>{d['emoji']} {d['name']}</b>

💰 Цена: <b>{price_str}</b>
⏰ Обновлено: {update_text}

<b>📈 Индикаторы:</b>
Volatile: <code>{d['volatile']:.4f}</code> ({bb_percent_display:.2f}%)
Trend: {trend_emoji} <b>{d['trend']}</b>

{"🟢 <b>BUY зона</b>" if d['volatile'] <= 0.0 else "🔴 <b>SELL зона</b>" if d['volatile'] >= 1.0 else "⚪ Нейтральная зона"}

Свечей: {len(d['candles'])}"""


def get_debug_bb_text(asset_key):
    """Детальная диагностика BB"""
    d = assets_data[asset_key]
    
    if len(d['candles']) < settings['volatile_length']:
        return "⚠️ Недостаточно свечей для BB"
    
    prices = [c['close'] for c in d['candles']]
    recent = prices[-settings['volatile_length']:]
    
    # Считаем обе версии
    upper_pop, lower_pop, basis_pop, stdev_pop = bollinger_bands(
        prices, settings['volatile_length'], settings['volatile_mult'], use_population=True
    )
    upper_sample, lower_sample, basis_sample, stdev_sample = bollinger_bands(
        prices, settings['volatile_length'], settings['volatile_mult'], use_population=False
    )
    
    volatile_pop = bb_percent(d['price'], upper_pop, lower_pop)
    volatile_sample = bb_percent(d['price'], upper_sample, lower_sample)
    
    price_str = f"${d['price']:,.2f}" if asset_key == "BTCUSD" else f"${d['price']:.2f}"
    
    msg = f"""<b>🔍 DEBUG BB - {d['emoji']} {d['name']}</b>

<b>Настройки:</b>
Period: {settings['volatile_length']}
Multiplier: {settings['volatile_mult']}
Цена сейчас: {price_str}

<b>📊 POPULATION StdDev (делим на n={settings['volatile_length']}):</b>
BB %B: <code>{volatile_pop:.6f}</code> ({volatile_pop*100:.2f}%)
Upper: ${upper_pop:.2f}
Basis: ${basis_pop:.2f}
Lower: ${lower_pop:.2f}
StdDev: ${stdev_pop:.4f}

<b>📊 SAMPLE StdDev (делим на n-1={settings['volatile_length']-1}):</b>
BB %B: <code>{volatile_sample:.6f}</code> ({volatile_sample*100:.2f}%)
Upper: ${upper_sample:.2f}
Basis: ${basis_sample:.2f}
Lower: ${lower_sample:.2f}
StdDev: ${stdev_sample:.4f}

<b>Сравни с TradingView!</b>
Если TradingView = {volatile_pop*100:.2f}% → используем POPULATION
Если TradingView = {volatile_sample*100:.2f}% → используем SAMPLE

Всего свечей: {len(d['candles'])}
Последняя свеча: {d['last_candle_time']}"""
    
    return msg


def check_signal(asset_key):
    """Проверка сигнала для актива"""
    asset = assets_data[asset_key]
    
    print(f"\n{'='*60}")
    print(f"📊 Проверка: {asset['emoji']} {asset['name']}")
    
    # Получаем свечи
    if asset_key == "BTCUSD":
        candles = get_btc_candles()
    else:
        candles = get_gold_candles()
    
    if candles is None or len(candles) == 0:
        print(f"   ⚠️ Не удалось получить свечи")
        return False
    
    asset["candles"] = candles
    
    last_candle = candles[-1]
    current_price = last_candle["close"]
    candle_time = last_candle["datetime"]
    
    # Проверка на новую свечу
    if candle_time == asset["last_candle_time"]:
        print(f"   ⏸️ Та же свеча: {candle_time}")
        asset["price"] = current_price
        asset["last_update"] = time.time()
        return False
    
    print(f"   ✅ НОВАЯ СВЕЧА: {candle_time}")
    asset["last_candle_time"] = candle_time
    
    # Извлекаем цены
    prices = [c["close"] for c in candles]
    
    # Проверка достаточности данных
    min_required = max(settings["volatile_length"] + 10, settings["trend_smooth"] + 10)
    if len(prices) < min_required:
        print(f"   ⚠️ Мало данных: {len(prices)}/{min_required}")
        asset["price"] = current_price
        asset["last_update"] = time.time()
        return False
    
    # === РАСЧЁТ ИНДИКАТОРОВ ===
    
    # 1. Nadaraya-Watson (Trend)
    print(f"   🔄 Расчёт Trend...")
    nw_last_3 = nadaraya_watson(prices, h=settings["trend_smooth"])
    
    if nw_last_3 and len(nw_last_3) >= 3:
        trend_up = nw_last_3[-1] > nw_last_3[-2]
        trend_down = nw_last_3[-1] < nw_last_3[-2]
        print(f"   📈 NW: {nw_last_3[-3]:.2f} → {nw_last_3[-2]:.2f} → {nw_last_3[-1]:.2f}")
    else:
        trend_up = False
        trend_down = False
        print(f"   ⚠️ Trend не рассчитан")
    
    # 2. Bollinger Bands (Volatile)
    print(f"   🔄 Расчёт BB...")
    
    # Пробуем POPULATION (делим на n)
    upper, lower, basis, stdev = bollinger_bands(
        prices, 
        length=settings["volatile_length"], 
        mult=settings["volatile_mult"],
        use_population=True  # ← POPULATION StdDev
    )
    
    if upper is None or lower is None:
        print(f"   ⚠️ BB не готов")
        asset["price"] = current_price
        asset["last_update"] = time.time()
        return False
    
    volatile = bb_percent(current_price, upper, lower)
    
    # Также считаем SAMPLE для сравнения
    upper_sample, lower_sample, basis_sample, stdev_sample = bollinger_bands(
        prices, 
        length=settings["volatile_length"], 
        mult=settings["volatile_mult"],
        use_population=False  # ← SAMPLE StdDev
    )
    volatile_sample = bb_percent(current_price, upper_sample, lower_sample) if upper_sample else 0
    
    # Форматирование цены
    price_display = f"${current_price:,.2f}" if asset_key == "BTCUSD" else f"${current_price:.2f}"
    
    print(f"   💰 Цена: {price_display}")
    print(f"   📊 BB Upper: ${upper:.2f}")
    print(f"   📊 BB Basis: ${basis:.2f}")
    print(f"   📊 BB Lower: ${lower:.2f}")
    print(f"   📊 StdDev: ${stdev:.4f}")
    print(f"   📈 BB %B POPULATION (n): {volatile:.6f} ({volatile*100:.2f}%)")
    print(f"   📈 BB %B SAMPLE (n-1): {volatile_sample:.6f} ({volatile_sample*100:.2f}%)")
    print(f"   🎯 Trend: {'UP 🟢' if trend_up else 'DOWN 🔴' if trend_down else 'FLAT ⚪'}")
    
    # Обновляем данные актива
    asset["price"] = current_price
    asset["volatile"] = volatile
    asset["trend"] = "UP" if trend_up else "DOWN" if trend_down else "FLAT"
    asset["upper"] = upper
    asset["lower"] = lower
    asset["basis"] = basis
    asset["stdev"] = stdev
    asset["last_update"] = time.time()
    
    # === СИГНАЛЫ ===
    if candle_time != asset.get("last_signal_candle"):
        # BUY: BB %B <= 0% (цена ниже/на нижней полосе) + Trend UP
        if volatile <= 0.0 and trend_up:
            msg = f"""🟢 <b>{asset['emoji']} {asset['name']} BUY SIGNAL</b>

💰 {price_display}
BB %B: {volatile:.4f} ({volatile*100:.2f}%)
Trend: UP 🟢

BB Lower: ${lower:.2f}
Цена пробила нижнюю полосу!

🕐 {candle_time}"""
            send_message(msg)
            print(f"   🟢 BUY SIGNAL!")
            asset["last_signal_candle"] = candle_time
            
        # SELL: BB %B >= 100% (цена выше/на верхней полосе) + Trend DOWN
        elif volatile >= 1.0 and trend_down:
            msg = f"""🔴 <b>{asset['emoji']} {asset['name']} SELL SIGNAL</b>

💰 {price_display}
BB %B: {volatile:.4f} ({volatile*100:.2f}%)
Trend: DOWN 🔴

BB Upper: ${upper:.2f}
Цена пробила верхнюю полосу!

🕐 {candle_time}"""
            send_message(msg)
            print(f"   🔴 SELL SIGNAL!")
            asset["last_signal_candle"] = candle_time
        else:
            print(f"   ⚪ Нет сигнала (BB %B: {volatile*100:.1f}%)")
    
    return True


def handle_messages():
    """Обработка команд Telegram"""
    global current_asset
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    offset = 0
    
    print("📱 Обработчик сообщений запущен\n")
    
    while True:
        try:
            params = {"offset": offset, "timeout": 30}
            r = requests.get(url, params=params, timeout=35).json()
            
            if r.get("ok") and r.get("result"):
                for update in r["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip()
                        
                        if text == "/start":
                            send_keyboard()
                            send_message("✅ Бот запущен!")
                        
                        elif text in ["🪙 Золото", "/gold"]:
                            current_asset = "XAUUSD"
                            send_message(get_status_text("XAUUSD"))
                        
                        elif text in ["₿ Bitcoin", "/btc"]:
                            current_asset = "BTCUSD"
                            send_message(get_status_text("BTCUSD"))
                        
                        elif text in ["📊 Статус", "/status"]:
                            send_message(get_status_text(current_asset))
                        
                        elif text in ["💰 Цена", "/price"]:
                            asset = assets_data[current_asset]
                            price_str = f"${asset['price']:,.2f}" if current_asset == "BTCUSD" else f"${asset['price']:.2f}"
                            send_message(f"{asset['emoji']} <b>{price_str}</b>\n\nBB %B: {asset['volatile']*100:.2f}%")
                        
                        elif text in ["📈 Индикаторы", "/indicators"]:
                            send_message(get_status_text(current_asset))
                        
                        elif text in ["🔄 Обновить", "/refresh"]:
                            send_message("⏳ Обновляю...")
                            check_signal(current_asset)
                            send_message(get_status_text(current_asset))
                        
                        elif text in ["🔍 DEBUG BB", "/debug"]:
                            send_message(get_debug_bb_text(current_asset))
                        
                        elif text == "/all":
                            send_message("⏳ Обновляю все активы...")
                            for asset_key in assets_data.keys():
                                check_signal(asset_key)
                            
                            msg = "✅ <b>ВСЕ АКТИВЫ</b>\n\n"
                            for key, asset in assets_data.items():
                                trend_emoji = "🟢" if asset["trend"] == "UP" else "🔴" if asset["trend"] == "DOWN" else "⚪"
                                price_str = f"${asset['price']:,.2f}" if key == "BTCUSD" else f"${asset['price']:.2f}"
                                msg += f"{asset['emoji']} {asset['name']}: {price_str} | {trend_emoji} | BB:{asset['volatile']*100:.1f}%\n"
                            send_message(msg)
        
        except Exception as e:
            print(f"⚠️ Handler error: {e}")
            time.sleep(5)


def monitoring_loop():
    """Основной цикл мониторинга"""
    print(f"🔄 Мониторинг запущен (каждые {settings['check_interval']}с)\n")
    
    while True:
        print(f"\n⏰ [{time.strftime('%H:%M:%S')}] === ПРОВЕРКА ===")
        
        for asset_key in ["XAUUSD", "BTCUSD"]:
            try:
                check_signal(asset_key)
            except Exception as e:
                print(f"❌ Ошибка {asset_key}: {e}")
        
        print(f"\n{'='*60}")
        print(f"⏳ Следующая проверка через {settings['check_interval']}с")
        print(f"{'='*60}")
        
        time.sleep(settings["check_interval"])


if __name__ == "__main__":
    print("="*80)
    print("🚀 ТРЕЙДИНГ БОТ - BB %B ТОЧНАЯ ВЕРСИЯ")
    print("="*80)
    print(f"📊 Золото: Twelve Data API")
    print(f"📊 Bitcoin: CryptoCompare API")
    print(f"⚙️ BB Period: {settings['volatile_length']}, Multiplier: {settings['volatile_mult']}")
    print(f"⚙️ TF: {settings['timeframe']}, проверка: {settings['check_interval']}с")
    print("="*80 + "\n")
    
    # Загрузка начальных данных
    print("🔄 Загрузка данных...\n")
    for asset_key in ["XAUUSD", "BTCUSD"]:
        try:
            check_signal(asset_key)
        except Exception as e:
            print(f"⚠️ Ошибка {asset_key}: {e}")
    
    print("\n✅ Данные загружены!\n")
    
    # Стартовое сообщение
    send_keyboard()
    
    gold_price = f"${assets_data['XAUUSD']['price']:.2f}" if assets_data['X
