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
        print("❌ 잘못된 웹훅 요청입니다", flush=True)
        return {"error": "unauthorized"}, 403

    signal = data.get("signal")
    print(f"✅ Signal received: {signal}", flush=True)

    if signal == "BUY":
        place_order("buy")
    elif signal == "TP":
        place_order("close")
    else:
        print("❌ Unknown signal", flush=True)
        return {"error": "unknown signal"}, 400

    return {"status": "success"}, 200

def get_balance():
    url = "https://www.okx.com/api/v5/account/balance?ccy=USDT"
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    method = "GET"
    request_path = "/api/v5/account/balance?ccy=USDT"

    pre_hash = timestamp + method + request_path
    signature = base64.b64encode(
        hmac.new(os.getenv("OKX_API_SECRET").encode(), pre_hash.encode(), hashlib.sha256).digest()
    ).decode()

    headers = {
        "OK-ACCESS-KEY": os.getenv("OKX_API_KEY"),
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": os.getenv("OKX_PASSPHRASE"),
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        usdt_balance = float(data['data'][0]['details'][0]['availBal'])
        print(f"💰 사용 가능한 USDT 잔고: {usdt_balance}", flush=True)
        return usdt_balance
    else:
        print("❌ 잔고 조회 실패:", response.status_code, response.text, flush=True)
        return 0.0

def place_order(action):
    api_key = os.getenv("OKX_API_KEY")
    api_secret = os.getenv("OKX_API_SECRET")
    passphrase = os.getenv("OKX_PASSPHRASE")
    symbol = os.getenv("SYMBOL")
    side = os.getenv("POSITION_SIDE")  # long / short
    leverage = float(os.getenv("LEVERAGE", "100"))
    trade_percent = float(os.getenv("TRADE_PERCENT", "0.001"))  # 0.001 = 0.1%

    url_path = "/api/v5/trade/order"
    url = "https://www.okx.com" + url_path
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())

    if action == "buy":
        side_api = "buy"
    elif action == "close":
        side_api = "sell"
    else:
        print("❌ Unknown action", flush=True)
        return

    # 실시간 잔고 기반 진입금 계산
    usdt_balance = get_balance()
    cost = usdt_balance * trade_percent
    order_usdt_value = cost * leverage

    # 실시간 가격 조회
    ticker_resp = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={symbol}")
    if ticker_resp.status_code != 200:
        print("❌ 시세 조회 실패", flush=True)
        return
    price = float(ticker_resp.json()['data'][0]['last'])

    amount = round(order_usdt_value / price, 6)

    # 최소 주문 수량 보정
    min_amount = 0.001
    if amount < min_amount:
        print(f"⚠️ 최소 주문 수량보다 작음. 강제로 {min_amount} BTC로 주문합니다.", flush=True)
        amount = min_amount

    print(f"🎯 현재 시세: {price} USDT", flush=True)
    print(f"🎯 내가 설정한 Cost (USDT): {cost:.4f}", flush=True)
    print(f"🎯 레버리지 포함 주문 총액: {order_usdt_value:.2f} USDT", flush=True)
    print(f"🎯 실제 주문 수량 (BTC): {amount}", flush=True)

    body = {
        "instId": symbol,
        "tdMode": "cross",
        "side": side_api,
        "ordType": "market",
        "posSide": side,
        "sz": str(amount)
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

    print("📦 요청 바디:", body_json, flush=True)
    print("📦 헤더 정보:", headers, flush=True)

    response = requests.post(url, headers=headers, data=body_json)
    print("✅ OKX 응답:", response.status_code, response.text, flush=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
