import os
import time
import requests
import pandas as pd
from pybit.unified_trading import HTTP

print("🚀 Bot Starting...")

# =========================
# ENV VARIABLES (RAILWAY ONLY)
# =========================
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not all([API_KEY, API_SECRET, BOT_TOKEN, CHAT_ID]):
    print("❌ Missing Railway environment variables")
    exit()

# =========================
# BYBIT CONNECTION
# =========================
session = HTTP(
    testnet=True,   # change to False if using real account
    api_key=API_KEY,
    api_secret=API_SECRET
)

symbol = BTC/USDT
running = True
last_update_id = 0

# =========================
# TELEGRAM
# =========================
def send_msg(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print("Telegram error:", e)

send_msg("🚀 Bot Online - Railway Active")

# =========================
# TELEGRAM COMMANDS
# =========================
def check_commands():
    global running, last_update_id

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        res = requests.get(url).json()

        for update in res.get("result", []):
            update_id = update["update_id"]

            if update_id <= last_update_id:
                continue

            last_update_id = update_id

            msg = update["message"]["text"].lower()

            if msg == "start":
                running = True
                send_msg("✅ Bot STARTED")

            elif msg == "stop":
                running = False
                send_msg("⛔ Bot STOPPED")

            elif msg == "status":
                send_msg(f"📊 Status: {'RUNNING 🟢' if running else 'STOPPED 🔴'}")

    except Exception as e:
        print("Command error:", e)

# =========================
# MARKET DATA
# =========================
def get_data():
    k = session.get_kline(
        category="linear",
        symbol=symbol,
        interval="5",
        limit=100
    )

    df = pd.DataFrame(k["result"]["list"])
    df = df.iloc[:, :5]
    df.columns = ["time", "open", "high", "low", "close"]
    df = df.astype(float)

    return df

# =========================
# INDICATORS (YOUR STRATEGY)
# =========================
def indicators(df):
    # Bollinger Bands
    df["mid"] = df["close"].rolling(20).mean()
    df["std"] = df["close"].rolling(20).std()
    df["upper"] = df["mid"] + 2 * df["std"]
    df["lower"] = df["mid"] - 2 * df["std"]

    # Stochastic
    low14 = df["low"].rolling(14).min()
    high14 = df["high"].rolling(14).max()
    df["stoch"] = 100 * (df["close"] - low14) / (high14 - low14)

    # EMA Trend Filter
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    return df

# =========================
# TREND FILTER
# =========================
def trend(df):
    last = df.iloc[-1]

    if last["ema50"] > last["ema200"]:
        return "up"
    elif last["ema50"] < last["ema200"]:
        return "down"
    return "flat"

# =========================
# YOUR SIGNAL RULES
# =========================
def signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    mid_lower = (last["lower"] + last["mid"]) / 2
    mid_upper = (last["upper"] + last["mid"]) / 2

    # BUY RULE
    buy = (
        last["close"] > mid_lower and
        prev["stoch"] < 10 and
        last["stoch"] > prev["stoch"]
    )

    # SELL RULE
    sell = (
        last["close"] < mid_upper and
        prev["stoch"] > 90 and
        last["stoch"] < prev["stoch"]
    )

    if buy:
        return "buy"
    if sell:
        return "sell"
    return "hold"

# =========================
# ORDER EXECUTION (DEMO SAFE)
# =========================
def place_order(side, price):
    try:
        qty = 0.01  # adjust later for risk management

        if side == "Buy":
            sl = price * 0.98
            tp = price * 1.06
        else:
            sl = price * 1.02
            tp = price * 0.94

        session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=qty,
            takeProfit=tp,
            stopLoss=sl
        )

        send_msg(f"📊 {side} executed\nEntry: {price}\nTP: {tp}\nSL: {sl}")

    except Exception as e:
        send_msg(f"Order error: {e}")

# =========================
# MAIN LOOP
# =========================
while True:
    try:
        check_commands()

        if not running:
            time.sleep(5)
            continue

        df = get_data()
        df = indicators(df)

        sig = signal(df)
        tr = trend(df)
        price = df.iloc[-1]["close"]

        print("Signal:", sig, "| Trend:", tr)

        # ONLY TRADE WITH TREND
        if sig == "buy" and tr == "up":
            place_order("Buy", price)

        elif sig == "sell" and tr == "down":
            place_order("Sell", price)

        time.sleep(300)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
