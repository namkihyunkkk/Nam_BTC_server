from flask import Flask, request
import os
import requests
from dotenv import load_dotenv
import time
import hmac
import hashlib
import base64
import json

# 환경 변수 로드
load_dotenv()
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data or data.get("secret") != os.getenv("WEBHOOK_SECRET"):
        return {"error": "unauthorized"}, 403

    signal = data.get("signal")
    if signal == "BUY":
        print("✅ Signal received: BUY")
        place_order("buy")
    elif signal == "TP":
        print("✅ Signal received: TP (Close)")
        place_order("close")
    else:
        return {"error": "unknown signal"}, 400

    return {"status": "success"}, 200

def place_order(action):
    api_key = os.getenv("OKX_API_KEY")
    api_secret = os.getenv("OKX_API_SECRET")
    passphrase = os.getenv("OKX_PASSPHRASE")
    symbol = os.getenv("SYMBOL")
    side = os.getenv("POSITION_SIDE")  # long / short
    trade_amount = os.getenv("TRADE_AMOUNT", "1.0")  # USDT 기준
    leverage = os.getenv("LEVERAGE", "100")

    url_path = "/api/v5/trade/order"
    url = "https://www.okx.com" + url_path
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())

    if action == "buy":
        side_api = "buy"
        pos_side = side
    elif action == "close":
        side_api = "sell"
        pos_side = side
    else:
        print("❌ Unknown action")
        return

    print(f"🎯 실제 사용중인 진입 금액 (USDT): {trade_amount}")

    body = {
        "instId": symbol,
        "tdMode": "cross",
        "side": side_api,
        "ordType": "market",
        "posSide": pos_side,
        "ccy": "USDT",  # ✅ 중요: USDT 기준으로 주문하도록 명시
        "sz": trade_amount
    }

    body_json = json.dumps(body, separators=(',', ':'))
    pre_hash = timestamp + 'POST' + url_path + body_json

    signature = base64.b64encode(
        hmac.new(api_secret.encode(), pre_hash.encode(), hashlib.sha256).digest()
    ).decode()

    headers = {
        'Content-Type': 'application/json',
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase
    }

    print("📦 요청 바디:", body_json)
    print("📦 헤더 정보:", headers)

    response = requests.post(url, headers=headers, data=body_json)
    print("✅ OKX 응답:", response.status_code, response.text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
