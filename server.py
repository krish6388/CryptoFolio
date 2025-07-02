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

"""
    This file is used to run the backend server in flask and acts as a middle layer between the UI and the coindx ws
    in new_trade.py file

"""

symbol_subscriptions = set()
user_subs = {}   # {'session_id': set(eth, btc, doge)}
price_data = {}  # Holds latest price per symbol
active_processes = {}  # {'symbol_name': new_trade.py processObj}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")  # --> * enables access from anywhere

# Home Page route
@app.route('/')
def index():
    return render_template('index.html')

import requests
from flask import jsonify

@app.route("/symbols")
def get_symbols():
    # Call external API here
    external_api_url = "https://api.coindcx.com/exchange/v1/derivatives/futures/data/active_instruments?margin_currency_short_name[]=USDT"
    try:
        response = requests.get(external_api_url)
        response.raise_for_status()
        symbols = response.json()  
        return jsonify(symbols)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Handle the subscribe emit coming from frontend
@socketio.on('subscribe')
def handle_subscribe(data):
    symbol = data.get('symbol')
    sid = request.sid
    if symbol:
        symbol_subscriptions.add(symbol)

        # Check if this is a new session id (browser)
        if sid not in user_subs:
            user_subs[sid] = set()
        # Add symbol to the corressponding session id
        user_subs[sid].add(symbol)

        print(symbol)
        # Run new_trade.py process for each symbol only once  --> Helps in reducing the server load 
        if symbol and symbol not in active_processes:

            process = subprocess.Popen([sys.executable, r"new_trade.py", symbol])  # --> Run in current venv 
            active_processes[symbol] = process

            emit('log', {"message": f"Subscribed to {symbol}"})

# Handles the unsubscribe emit from frontend
@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    symbol = data.get('symbol')
    sid = request.sid
    print('*** Unsubscribe Running')
    # print(data)
    # print(symbol_subscriptions)
    if symbol and sid in user_subs and symbol in user_subs[sid]:
        
        user_subs[sid].discard(symbol)

        process = active_processes.get(symbol)  # --> Check if symbol has an ongoing process

        # Kill Process only when no sid has subcribed to the symbol
        if process and symbol not in set.union(*user_subs.values()):
            process.terminate()  # sends SIGTERM
            process.wait()       # wait for graceful exit
            del active_processes[symbol]
            

            emit('log', {"message": f"Unsubscribed from {symbol}"}, to=sid)
        elif process:
            emit('log', {"message": f"Unsubscribed from {symbol}"}, to=sid)
        else:
            emit('log', {"message": f"No active process found for {symbol}"}, to=sid)
        
    else:
        emit('log', {"message": f"Symbol {symbol} was not subscribed by you."}, to=sid)


# Handle the live price from new_trade.py
@socketio.on('external_table_update')
def handle_external_trade(data):
    
    print("✅ Got external_table_update:", data)
    symbol = data.get("symbol")

    # Iterate the user subscription dictionary
    for sid, symbols in user_subs.items():

        if symbol + '@trades-futures' in symbols:
            print('Emiting Data to html')
            socketio.emit('trade_update', data, to=sid)


if __name__ == '__main__':
    print('Flask WebApp Server: Starting ...') 
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
