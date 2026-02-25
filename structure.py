import requests
import pandas as pd
import time
from datetime import datetime

# ==============================
# CONFIG
# ==============================

SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT"
}

START_CAPITAL = 100
RISK_PERCENT = 0.01
TELEGRAM_TOKEN = "8788777480:AAG3G_A2Wut1vryRKexpy2l5FqVmJjGCXtM"
TELEGRAM_CHAT_ID = "7225721600"

capital = START_CAPITAL
open_positions = {}
last_trade_hour = None

# ==============================
# TELEGRAM
# ==============================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except:
        pass

# ==============================
# DATA
# ==============================

def get_klines(symbol, interval):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": 200}
        data = requests.get(url, params=params).json()

        if not data or isinstance(data, dict):
            return None

        df = pd.DataFrame(data)
        df = df.iloc[:, 0:6]
        df.columns = ["time","open","high","low","close","volume"]
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        return df
    except:
        return None

# ==============================
# STRUCTURE FUNCTIONS
# ==============================

def find_swings(df):
    swings_high = []
    swings_low = []

    for i in range(2, len(df)-2):
        if df["high"][i] > df["high"][i-1] and df["high"][i] > df["high"][i-2] and \
           df["high"][i] > df["high"][i+1] and df["high"][i] > df["high"][i+2]:
            swings_high.append((i, df["high"][i]))

        if df["low"][i] < df["low"][i-1] and df["low"][i] < df["low"][i-2] and \
           df["low"][i] < df["low"][i+1] and df["low"][i] < df["low"][i+2]:
            swings_low.append((i, df["low"][i]))

    return swings_high, swings_low

# ==============================
# SIGNAL
# ==============================

def check_signal(symbol):

    df_1h = get_klines(symbol, "1h")
    df_15m = get_klines(symbol, "15m")

    if df_1h is None or df_15m is None:
        return None

    highs_1h, lows_1h = find_swings(df_1h)
    highs_15m, lows_15m = find_swings(df_15m)

    if len(highs_1h) < 2 or len(lows_1h) < 2:
        return None

    # Determine trend
    if highs_1h[-1][1] > highs_1h[-2][1] and lows_1h[-1][1] > lows_1h[-2][1]:
        trend = "UP"
    elif highs_1h[-1][1] < highs_1h[-2][1] and lows_1h[-1][1] < lows_1h[-2][1]:
        trend = "DOWN"
    else:
        return None

    last_price = df_15m["close"].iloc[-1]

    # LONG
    if trend == "UP" and highs_15m:
        last_swing_high = highs_15m[-1][1]
        last_swing_low = lows_15m[-1][1] if lows_15m else None

        if last_price > last_swing_high and last_swing_low:
            return ("LONG", last_price, last_swing_low)

    # SHORT
    if trend == "DOWN" and lows_15m:
        last_swing_low = lows_15m[-1][1]
        last_swing_high = highs_15m[-1][1] if highs_15m else None

        if last_price < last_swing_low and last_swing_high:
            return ("SHORT", last_price, last_swing_high)

    return None

# ==============================
# TRADE MANAGEMENT
# ==============================

def open_trade(coin, direction, entry, stop):
    global capital, last_trade_hour

    risk_amount = capital * RISK_PERCENT
    stop_distance = abs(entry - stop)
    size = risk_amount / stop_distance

    if direction == "LONG":
        target = entry + stop_distance * 2
    else:
        target = entry - stop_distance * 2

    open_positions[coin] = {
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "target": target,
        "size": size
    }

    last_trade_hour = datetime.utcnow().hour

    send_telegram(
        f"📈 STRUCTURE {coin} {direction}\n"
        f"Entry: {round(entry,4)}\n"
        f"Stop: {round(stop,4)}\n"
        f"Target: {round(target,4)}"
    )

def check_exit(coin):
    global capital

    position = open_positions[coin]
    df = get_klines(SYMBOLS[coin], "15m")
    if df is None:
        return

    price = df["close"].iloc[-1]

    if position["direction"] == "LONG":
        if price <= position["stop"] or price >= position["target"]:
            pnl = (price - position["entry"]) * position["size"]
        else:
            return
    else:
        if price >= position["stop"] or price <= position["target"]:
            pnl = (position["entry"] - price) * position["size"]
        else:
            return

    capital += pnl

    send_telegram(
        f"💰 STRUCTURE CLOSED {coin}\n"
        f"PnL: {round(pnl,2)}\n"
        f"Capital: {round(capital,2)}"
    )

    del open_positions[coin]

# ==============================
# MAIN LOOP
# ==============================

send_telegram("🚀 Pure Structure Engine Online")

while True:
    try:
        current_hour = datetime.utcnow().hour

        for coin in SYMBOLS.keys():

            if coin in open_positions:
                check_exit(coin)

            else:
                if last_trade_hour != current_hour:
                    signal = check_signal(SYMBOLS[coin])
                    if signal:
                        direction, entry, stop = signal
                        open_trade(coin, direction, entry, stop)

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
