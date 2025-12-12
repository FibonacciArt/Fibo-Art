import requests
import time
import threading

API_KEY = "5eba3772052948fca1bc270b9504101a"
BOT_TOKEN = "8494428945:AAHzBKk38mXzbFIEGK5mrJ45puRJT9svnEg"
CHAT_ID = "1464388096"

# Глобальные переменные для хранения последних данных
last_data = {
    "price": 0,
    "bb_pct": 0,
    "trend": "FLAT",
    "upper": 0,
    "lower": 0,
    "time": ""
}


def get_prices():
    """Получить последние 60 цен"""
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1min&outputsize=60&apikey={API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        if "values" not in r:
            print(f"API error: {r}")
            return None
        prices = [float(v["close"]) for v in reversed(r["values"])]
        return prices
    except Exception as e:
        print(f"Error: {e}")
        return None


def bollinger_bands(prices, length=25, std_dev=2.1):
    """Bollinger Bands"""
    if len(prices) < length:
        return None, None
    
    recent = prices[-length:]
    ma = sum(recent) / length
    variance = sum((x - ma) ** 2 for x in recent) / length
    sd = variance ** 0.5
    
    upper = ma + sd * std_dev
    lower = ma - sd * std_dev
    return upper, lower


def bb_percent(price, upper, lower):
    """BB%B индикатор"""
    if upper == lower:
        return 0.5
    return (price - lower) / (upper - lower)


def send_message(text, reply_markup=None):
    """Отправить сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"Error sending: {e}")


def send_keyboard():
    """Отправить клавиатуру с кнопками"""
    keyboard = {
        "keyboard": [
            [{"text": "📊 Статус"}],
            [{"text": "💰 Цена"}, {"text": "📈 Индикаторы"}],
            [{"text": "🔔 Последний сигнал"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }
    send_message("Выбери команду:", reply_markup=keyboard)


def get_status_text():
    """Получить текст со статусом"""
    d = last_data
    trend_emoji = "🟢" if d["trend"] == "UP" else "🔴" if d["trend"] == "DOWN" else "⚪"
    
    text = f"""
<b>📊 СТАТУС XAUUSD</b>

💰 Цена: <b>${d['price']:.2f}</b>
⏰ Время: {d['time']}

<b>📈 Индикаторы:</b>
BB%B: <code>{d['bb_pct']:.3f}</code>
Верхняя полоса: ${d['upper']:.2f}
Нижняя полоса: ${d['lower']:.2f}

Тренд NW: {trend_emoji} <b>{d['trend']}</b>

{"🟢 <b>BUY зона</b>" if d['bb_pct'] <= 0.05 else "🔴 <b>SELL зона</b>" if d['bb_pct'] >= 0.95 else "⚪ Нейтральная зона"}
"""
    return text.strip()


def check_signal():
    """Проверить сигнал и обновить данные"""
    prices = get_prices()
    if not prices or len(prices) < 30:
        print("Not enough data")
        return
    
    # Тренд
    recent_5 = sum(prices[-5:]) / 5
    previous_5 = sum(prices[-10:-5]) / 5
    trend_up = recent_5 > previous_5
    trend_down = recent_5 < previous_5
    
    # Bollinger Bands
    upper, lower = bollinger_bands(prices)
    if upper is None:
        print("BB not ready")
        return
    
    current_price = prices[-1]
    bb_pct = bb_percent(current_price, upper, lower)
    
    # Обновляем глобальные данные
    last_data["price"] = current_price
    last_data["bb_pct"] = bb_pct
    last_data["trend"] = "UP" if trend_up else "DOWN" if trend_down else "FLAT"
    last_data["upper"] = upper
    last_data["lower"] = lower
    last_data["time"] = time.strftime('%H:%M:%S')
    
    print(f"Price: {current_price:.2f}, BB%B: {bb_pct:.3f}, Trend: {last_data['trend']}")
    
    threshold = 0.05
    
    # Сигналы
    if bb_pct <= threshold and trend_up:
        send_message(f"🟢 <b>XAUUSD BUY SIGNAL</b>\n\nPrice: ${current_price:.2f}\nBB%B: {bb_pct:.3f}\nTrend: UP")
        print("BUY signal!")
    elif bb_pct >= (1 - threshold) and trend_down:
        send_message(f"🔴 <b>XAUUSD SELL SIGNAL</b>\n\nPrice: ${current_price:.2f}\nBB%B: {bb_pct:.3f}\nTrend: DOWN")
        print("SELL signal!")
    else:
        print("No signal")


def handle_messages():
    """Обработка входящих сообщений"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    offset = 0
    
    while True:
        try:
            params = {"offset": offset, "timeout": 30}
            r = requests.get(url, params=params, timeout=35).json()
            
            if r.get("ok") and r.get("result"):
                for update in r["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"]
                        
                        if text == "/start":
                            send_keyboard()
                            send_message("✅ Бот запущен! Выбери команду из меню.")
                        
                        elif text in ["📊 Статус", "/status"]:
                            send_message(get_status_text())
                        
                        elif text in ["💰 Цена", "/price"]:
                            send_message(f"💰 Текущая цена XAUUSD: <b>${last_data['price']:.2f}</b>")
                        
                        elif text in ["📈 Индикаторы", "/indicators"]:
                            trend_emoji = "🟢" if last_data["trend"] == "UP" else "🔴" if last_data["trend"] == "DOWN" else "⚪"
                            send_message(f"""
<b>📈 Индикаторы XAUUSD:</b>

BB%B: <code>{last_data['bb_pct']:.3f}</code>
Верхняя полоса: ${last_data['upper']:.2f}
Нижняя полоса: ${last_data['lower']:.2f}
Тренд: {trend_emoji} <b>{last_data['trend']}</b>
""")
                        
                        elif text in ["🔔 Последний сигнал", "/signal"]:
                            send_message(get_status_text())
        
        except Exception as e:
            print(f"Error in message handler: {e}")
            time.sleep(5)


def monitoring_loop():
    """Основной цикл мониторинга"""
    while True:
        print(f"\n--- Проверка {time.strftime('%H:%M:%S')} ---")
        check_signal()
        time.sleep(60)


if __name__ == "__main__":
    print("=== БОТ ЗАПУЩЕН ===")
    
    # Отправляем клавиатуру при старте
    send_keyboard()
    send_message("✅ <b>Бот запущен и работает!</b>\n\nИспользуй кнопки для получения информации.")
    
    # Запускаем обработчик сообщений в отдельном потоке
    message_thread = threading.Thread(target=handle_messages, daemon=True)
    message_thread.start()
    
    # Запускаем основной цикл мониторинга
    monitoring_loop()
