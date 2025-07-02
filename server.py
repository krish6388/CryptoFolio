# server.py
import subprocess
import contextlib
import sys
import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
# import eventlet
import asyncio
import json
from datetime import datetime
import socketio as client_socketio
import ssl
import os

# Required for Flask-SocketIO with eventlet
# eventlet.monkey_patch()

# WebSocket client setup for CoinDCX
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

client_sio = client_socketio.AsyncClient(ssl_verify=False)
symbol_subscriptions = set()
user_subs = {}
price_data = {}  # Holds latest price per symbol
active_processes = {}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('subscribe')
def handle_subscribe(data):
    symbol = data.get('symbol')
    sid = request.sid
    if symbol:
        symbol_subscriptions.add(symbol)
        if sid not in user_subs:
            user_subs[sid] = set()
        user_subs[sid].add(symbol)

        # use eventlet.spawn instead of socketio.start_background_task for true async emit
        # def sync_emit():
        #     if client_sio.connected:
        #         coro = client_sio.emit('join', {'channelName': [symbol]})
        #         asyncio.get_event_loop().create_task(coro)
        #     else:
        #         print("❗ CoinDCX WebSocket not yet connected.")

        # eventlet.spawn(sync_emit)
        # channel = f"B-{symbol}@trades-futures"
        print(symbol)
        if symbol and symbol not in active_processes:
            print(os.listdir('/opt/render/project/src'))

            process = subprocess.Popen([sys.executable, r"new_trade.py", symbol])
            active_processes[symbol] = process

            emit('log', {"message": f"Subscribed to {symbol}"})


@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    symbol = data.get('symbol')
    sid = request.sid
    print('*** Unsubscribe')
    print(data)
    print(symbol_subscriptions)
    if symbol and sid in user_subs and symbol in user_subs[sid]:
        # symbol_subscriptions.remove(symbol)
        if sid in user_subs and symbol in user_subs[sid]:
            user_subs[sid].discard(symbol)
        else:
            emit('log', {"message": f"Symbol {symbol} was not subscribed by you."}, to=sid)
            return

        process = active_processes.get(symbol)

        if process and symbol not in set.union(*user_subs.values()):
            process.terminate()  # sends SIGTERM
            process.wait()       # wait for graceful exit
            del active_processes[symbol]
            # socketio.emit('remove_row', {'symbol': symbol})

            emit('log', {"message": f"Unsubscribed from {symbol}"}, to=sid)
        elif process:
            emit('log', {"message": f"Unsubscribed from {symbol}"}, to=sid)
        else:
            emit('log', {"message": f"No active process found for {symbol}"}, to=sid)
        # sio.emit('leave', { 'channelName' : 'coindcx' })
        # emit("external_table_update", {
        #     "symbol": symbol,
        #     "price": price,
        #     "quantity": quantity,
        #     "time": timestamp.strftime("%H%M%S")
        # })
    else:
        emit('log', {"message": f"Symbol {symbol} was not subscribed by you."}, to=sid)

@socketio.on('external_table_update')
def handle_external_trade(data):
    # socketio.emit('trade_update', data)
    print("✅ Got external_table_update:", data)
    symbol = data.get("symbol")
    for sid, symbols in user_subs.items():
        print(symbol)
        print(symbols)
        if symbol + '@trades-futures' in symbols:
            print('Emiting Data to html')
            socketio.emit('trade_update', data, to=sid)

# @client_sio.on('new-trade')
# async def on_new_trade(response):
#     try:
#         trade_data = json.loads(response['data'])
#         symbol = trade_data.get("s")
#         price = trade_data.get("p")
#         quantity = trade_data.get("q")
#         trade_time = datetime.fromtimestamp(trade_data.get("T") / 1000)

#         price_data[symbol] = {"price": price, "qty": quantity, "time": trade_time.isoformat()}

#         # Broadcast to all frontend clients
#         socketio.emit('trade_update', {
#             "symbol": symbol,
#             "price": price,
#             "quantity": quantity,
#             "time": trade_time.isoformat()
#         })
#     except Exception as e:
#         print(f"Error parsing trade: {e}")

# async def ping_task():
#     while True:
#         await asyncio.sleep(25)
#         await client_sio.emit('ping', {'data': 'Ping message'})

# async def coin_dcx_ws():
#     print("🚀 Attempting to connect to CoinDCX WebSocket...")
#     try:
#         await client_sio.connect('wss://stream.coindcx.com', transports=['websocket'])
#         print("✅ CoinDCX WebSocket connection established!")
#         asyncio.create_task(ping_task())
#         await client_sio.wait()
#     except Exception as e:
#         print(f"❌ Connection error: {e}")

#     # ping = None
#     # try:
#     #     await client_sio.connect('wss://stream.coindcx.com', transports=['websocket'])
#     #     ping = asyncio.create_task(ping_task())
#     #     await client_sio.wait()
#     # except Exception as e:
#     #     print(f"[{datetime.now()}] ❗ Connection error: {e}")
#     # finally:
#     #     if ping:
#     #         ping.cancel()
#     #         with contextlib.suppress(asyncio.CancelledError):
#     #             await ping

# def start_coin_dcx_ws():
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     loop.run_until_complete(coin_dcx_ws())

if __name__ == '__main__':
    # socketio.start_background_task(start_coin_dcx_ws)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
