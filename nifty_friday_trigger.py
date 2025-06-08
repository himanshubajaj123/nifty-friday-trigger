# =============================
# nifty_friday_trigger.py
# =============================
import os
import datetime
import requests
import yfinance as yf

# ──────────────────────────────────────────────────────────────────────────────
# 1) CONFIGURATION: read your Telegram token & chat ID from environment variables
#
#    TELEGRAM_BOT_TOKEN  = your bot token from BotFather
#    TELEGRAM_CHAT_ID    = your chat ID (where to send the alert)
# ──────────────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram_message(text: str):
    """
    Sends `text` to TELEGRAM_CHAT_ID using TELEGRAM_BOT_TOKEN.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    resp = requests.post(url, data=payload)
    if not resp.ok:
        print("Failed to send Telegram message:", resp.text)
    else:
        print("Telegram message sent.")

# ──────────────────────────────────────────────────────────────────────────────
# 2) FUNCTION to check the 4-week high / 2-week low on Friday close
# ──────────────────────────────────────────────────────────────────────────────

def check_nifty_weekly_trigger():
    """
    - Downloads the last 45 calendar days of Nifty 50 via yfinance.
    - Identifies the most recent Friday that has a trading bar.
    - Computes:
       * 4-week high = max High over the 20 trading days BEFORE that Friday
       * 2-week low  = min Low  over the 10 trading days BEFORE that Friday
    - Compares Friday's close to those levels.
    - Returns (is_friday_bar_available, message_text).
    """
    # STEP A: Is today a Friday?
    today = datetime.date.today()
    if today.weekday() != 4:  # 4 == Friday
        return False, f"Today is not Friday ({today.strftime('%A')}), skipping."

    # STEP B: Download recent data (~45 calendar days, ~30 trading days)
    ticker = "^NSEI"  # Nifty 50 ticker on Yahoo Finance
    df = yf.download(ticker, period="45d", interval="1d", progress=False)
    # Convert index to IST date objects
    df.index = df.index.tz_convert("Asia/Kolkata").date
    # Keep only the last 30 rows for safety
    df = df.tail(30)

    # STEP C: Find the most recent Friday bar in df.index
    if today not in df.index:
        # If today's Friday bar hasn't appeared yet (e.g. run before market close),
        # find the latest Friday in the existing index.
        fridays = [d for d in df.index if d.weekday() == 4]
        if not fridays:
            return True, "No Friday bar available yet."
        last_friday = max(fridays)
    else:
        last_friday = today

    friday_pos = list(df.index).index(last_friday)
    # Need ≥20 days before to compute 4-week high, and ≥10 days for 2-week low
    if friday_pos < 20:
        return True, "Not enough history to compute 4-week high / 2-week low."

    # STEP D: Lookback slices (exclude the Friday bar itself)
    lookback_4w = df.iloc[friday_pos - 20 : friday_pos]  # previous 20 trading days
    lookback_2w = df.iloc[friday_pos - 10 : friday_pos]  # previous 10 trading days

    high_4w = lookback_4w["High"].max()
    low_2w  = lookback_2w["Low"].min()
    friday_close = df.iloc[friday_pos]["Close"]

    # STEP E: Form the Telegram message
    msg_lines = [
        f"*Nifty 50 Friday Close Check — {last_friday:%Y-%m-%d}*",
        f"• 4-week high (prev 20 days): `{high_4w:.2f}`",
        f"• 2-week low (prev 10 days): `{low_2w:.2f}`",
        f"• Friday close: `{friday_close:.2f}`",
    ]

    if friday_close >= high_4w:
        msg_lines.append("\n✅ *Breakout*: Friday close is at or above the 4‑week high.")
    elif friday_close <= low_2w:
        msg_lines.append("\n🔻 *Breakdown*: Friday close is at or below the 2‑week low.")
    else:
        msg_lines.append("\n🔍 No trigger: Friday close did not break 4‑week high or 2‑week low.")

    final_text = "\n".join(msg_lines)
    return True, final_text

# ──────────────────────────────────────────────────────────────────────────────
# 3) MAIN ENTRYPOINT
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    is_friday, text = check_nifty_weekly_trigger()
    print(text)  # always print summary in the Action log
    if is_friday:
        # If you only want to send when there is a breakout/breakdown,
        # wrap send_telegram_message(...) in an if‑statement:
        # if "Breakout" in text or "Breakdown" in text: send_telegram_message(text)
        send_telegram_message(text)

