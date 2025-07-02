import socketio
import json
import asyncio
from datetime import datetime
import contextlib

import sys
import socketio

"""
    This file acts as a primary connector to coindx ws, join channels and get latest price updates.
    It catches data from coindcx ws and share it with flask backend i.e. server.py

"""

# Connected Flask Backend Server to recieve latest price from coindx ws
flask_sio = socketio.Client()
flask_sio.connect("https://cryptofolio-t9x7.onrender.com/") # Flask WebApp URL


# Changed the static channelName -> Args dependent
if len(sys.argv) > 1:
    channelName = sys.argv[1]
else:
    raw_symbol = "BTC_USDT"
    channelName = f"B-{raw_symbol}@trades-futures"

# ========== WebSocket Configuration ==========
socketEndpoint = 'wss://stream.coindcx.com'
# channelName = "B-BTC_USDT@trades-futures"
# channelName = "B-BTC_USDT@orderbook@50-futures"


# ========== Event Names ==========
# connect     - Triggered when socket connects
# disconnect  - Triggered when socket disconnects
# join        - Used to subscribe to a specific channel
# ping        - Custom event to keep connection alive
# new-trade   - Emits whenever a new trade is executed on a symbol
# =================================

# Initialize socket client with SSL verification disabled for CoinDCX
import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

sio = socketio.AsyncClient(
    logger=False, 
    engineio_logger=False,
    ssl_verify=False  # Disable SSL verification for CoinDCX endpoint
)


# Ping the server every 25 seconds to keep the connection alive
async def ping_task():
    try:
        while True:
            await asyncio.sleep(25)
            await sio.emit('ping', {'data': 'Ping message'})
            print(f"[{datetime.now()}] 🔄 Ping sent")
    except asyncio.CancelledError:
        print(f"[{datetime.now()}] ⚠️ Ping task cancelled")


# On successful connection, join the trade stream
@sio.event
async def connect():
    print(f"[{datetime.now()}] ✅ Connected to WebSocket")
    await sio.emit('join', {'channelName': [channelName]})
    print(f"[{datetime.now()}] 📡 Subscribed to: {channelName}")


# Handle new-trade events
@sio.on('new-trade')
async def on_new_trade(response):
    print(f"\n====== 📈 New Trade Received ({channelName}) ======")
    try:
        trade_data = json.loads(response['data'])

        symbol = trade_data.get("s")  # Symbol, e.g. B-ID_USDT
        price = trade_data.get("p")  # Trade price
        quantity = trade_data.get("q")  # Trade quantity
        trade_time = trade_data.get("T")  # Epoch ms timestamp

        # Convert timestamp to readable format
        timestamp = datetime.fromtimestamp(trade_time / 1000)


        print(f"[{timestamp}] {symbol} | Price: ₹{price} | Qty: {quantity}")

        # Emit the live price of symbol to flask backend
        flask_sio.emit("external_table_update", {
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "time": timestamp.strftime("%H%M%S")
        })
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error parsing trade data: {e}\nRaw: {response}")

# On disconnect
@sio.event
async def disconnect():
    print(f"[{datetime.now()}] 🔌 Disconnected")
    sio.emit('leave', { 'channelName' : channelName })


# Main function to run the client
async def main():
    ping = None
    try:
        await sio.connect(socketEndpoint, transports=['websocket'])
        ping = asyncio.create_task(ping_task())
        await sio.wait()
    except Exception as e:
        print(f"[{datetime.now()}] ❗ Connection error: {e}")
    finally:
        if ping:
            ping.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ping


# Entry point
if __name__ == '__main__':
    asyncio.run(main())
