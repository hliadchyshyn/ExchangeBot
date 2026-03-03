import logging
import os
import threading
import time

import telebot
from aiohttp import web

import mono
import banks

currencyDict = {840: 'USD', 978: 'EUR', 980: 'UAH'}

API_TOKEN = os.environ.get('TOKEN')
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST', 'exchangebot.duckdns.org')
WEBHOOK_URL = f'https://{WEBHOOK_HOST}/{API_TOKEN}/'
INTERNAL_PORT = int(os.environ.get('PORT', 8080))

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

bot = telebot.TeleBot(API_TOKEN)
app = web.Application()

_convert_state: dict = {}
_alert_state: dict = {}
_alerts: dict = {}  # {chat_id: [{'currency': str, 'direction': str, 'value': float}]}


# --- Background alert checker ---

def _check_alerts():
    while True:
        time.sleep(60)
        if not _alerts:
            continue
        try:
            usd = mono.get_exchange(840)
            eur = mono.get_exchange(978)
        except Exception:
            continue
        rates = {}
        if usd:
            rates['USD'] = usd['rateSell']
        if eur:
            rates['EUR'] = eur['rateSell']
        for chat_id in list(_alerts.keys()):
            remaining = []
            for alert in _alerts.get(chat_id, []):
                rate = rates.get(alert['currency'])
                if rate is None:
                    remaining.append(alert)
                    continue
                triggered = (
                    (alert['direction'] == '>' and rate > alert['value']) or
                    (alert['direction'] == '<' and rate < alert['value'])
                )
                if triggered:
                    try:
                        bot.send_message(
                            chat_id,
                            f'🔔 <b>{alert["currency"]}/UAH</b> is now <b>{rate}</b>\n'
                            f'Your alert: {alert["direction"]} {alert["value"]}',
                            parse_mode='HTML'
                        )
                    except Exception:
                        remaining.append(alert)
                else:
                    remaining.append(alert)
            if remaining:
                _alerts[chat_id] = remaining
            else:
                _alerts.pop(chat_id, None)


threading.Thread(target=_check_alerts, daemon=True).start()


# --- Webhook handler ---

async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    return web.Response(status=403)


app.router.add_post('/{token}/', handle)


# --- Keyboards ---

def main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('💱 Exchange', '📊 Rates')
    markup.row('🔄 Convert', '🔔 Alerts')
    markup.row('📈 History', '🏦 Best Rate')
    markup.row('₿ Crypto')
    return markup


def currency_inline_keyboard(callback_prefix: str, exclude: str = None):
    markup = telebot.types.InlineKeyboardMarkup()
    buttons = [
        telebot.types.InlineKeyboardButton(c, callback_data=f'{callback_prefix}-{c}')
        for c in ('UAH', 'USD', 'EUR') if c != exclude
    ]
    markup.add(*buttons)
    return markup


def alert_ccy_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton('USD', callback_data='alert-ccy-USD'),
        telebot.types.InlineKeyboardButton('EUR', callback_data='alert-ccy-EUR'),
    )
    return markup


# --- Message handlers ---

@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        '<b>MonoBank Exchange Bot</b>\n\n'
        '💱 <b>Exchange</b> — buy/sell rate for USD or EUR\n'
        '📊 <b>Rates</b> — all rates at a glance\n'
        '🔄 <b>Convert</b> — convert between UAH, USD, EUR\n'
        '🔔 <b>Alerts</b> — notify me when a rate crosses a threshold',
        parse_mode='HTML',
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=['exchange'])
@bot.message_handler(func=lambda m: m.text == '💱 Exchange')
def exchange_handler(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton('USD', callback_data='get-840'),
        telebot.types.InlineKeyboardButton('EUR', callback_data='get-978'),
    )
    bot.send_message(message.chat.id, 'Select currency:', reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == '📊 Rates')
def rates_handler(message):
    bot.send_chat_action(message.chat.id, 'typing')
    mono_usd = mono.get_exchange(840)
    mono_eur = mono.get_exchange(978)
    try:
        privat = banks.get_privat_rates()
    except Exception:
        privat = {}

    def row(label, mono_ex, priv):
        mono_str = f'{mono_ex["rateBuy"]} / {mono_ex["rateSell"]}' if mono_ex else '—'
        priv_str = f'{priv["buy"]} / {priv["sell"]}' if priv else '—'
        return f'<b>{label}</b>\nMono:   {mono_str}\nPrivat: {priv_str}'

    lines = [
        '<b>Buy / Sell rates</b>\n',
        row('USD / UAH', mono_usd, privat.get('USD')),
        row('EUR / UAH', mono_eur, privat.get('EUR')),
    ]
    bot.send_message(message.chat.id, '\n\n'.join(lines), parse_mode='HTML')


@bot.message_handler(func=lambda m: m.text == '₿ Crypto')
def crypto_handler(message):
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        rates = banks.get_binance_rates()
    except Exception:
        bot.send_message(message.chat.id, 'Could not fetch crypto rates. Try again later.')
        return
    labels = {
        'USDTUAH': 'USDT / UAH',
        'BTCUAH':  'Bitcoin / UAH',
        'ETHUAH':  'Ethereum / UAH',
        'SOLUAH':  'Solana / UAH',
    }
    lines = ['<b>₿ Binance rates</b>\n']
    for r in rates:
        label = labels.get(r['symbol'], r['symbol'])
        lines.append(f'{label}: <b>{r["price"]:,.2f}</b>')
    bot.send_message(message.chat.id, '\n'.join(lines), parse_mode='HTML')


@bot.message_handler(func=lambda m: m.text == '🔄 Convert')
def convert_handler(message):
    _convert_state[message.chat.id] = {'step': 'amount'}
    bot.send_message(message.chat.id, 'Enter the amount:')


@bot.message_handler(func=lambda m: _convert_state.get(m.chat.id, {}).get('step') == 'amount')
def handle_amount(message):
    try:
        amount = float(message.text.replace(',', '.'))
    except ValueError:
        bot.send_message(message.chat.id, 'Please enter a valid number.')
        return
    _convert_state[message.chat.id]['amount'] = amount
    _convert_state[message.chat.id]['step'] = 'from'
    bot.send_message(message.chat.id, 'Convert from:', reply_markup=currency_inline_keyboard('from'))


@bot.message_handler(func=lambda m: m.text == '🏦 Best Rate')
def best_rate_handler(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton('USD / UAH', callback_data='bestrate-USD'),
        telebot.types.InlineKeyboardButton('EUR / UAH', callback_data='bestrate-EUR'),
    )
    bot.send_message(message.chat.id, 'Find cheapest rate to buy:', reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == '📈 History')
def history_handler(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton('USD / UAH', callback_data='history-USD'),
        telebot.types.InlineKeyboardButton('EUR / UAH', callback_data='history-EUR'),
    )
    bot.send_message(message.chat.id, 'Select currency:', reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == '🔔 Alerts')
def alerts_menu(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton('➕ Add alert', callback_data='alert-add'),
        telebot.types.InlineKeyboardButton('📋 My alerts', callback_data='alert-list'),
    )
    bot.send_message(message.chat.id, 'Alerts:', reply_markup=markup)


@bot.message_handler(func=lambda m: _alert_state.get(m.chat.id, {}).get('step') == 'value')
def handle_alert_value(message):
    try:
        value = float(message.text.replace(',', '.'))
    except ValueError:
        bot.send_message(message.chat.id, 'Please enter a valid number.')
        return
    state = _alert_state.pop(message.chat.id)
    _alerts.setdefault(message.chat.id, []).append({
        'currency': state['currency'],
        'direction': state['direction'],
        'value': value,
    })
    bot.send_message(
        message.chat.id,
        f'✅ Alert set: <b>{state["currency"]}/UAH {state["direction"]} {value}</b>',
        parse_mode='HTML'
    )


# --- Helpers ---

def serialize_ex(ex_json):
    return (
        f'<b>{currencyDict[ex_json["currencyCodeA"]]} / UAH</b>\n\n'
        f'Buy: {ex_json["rateBuy"]}\n'
        f'Sell: {ex_json["rateSell"]}'
    )


def convert_amount(amount: float, from_ccy: str, to_ccy: str) -> float | None:
    if from_ccy == to_ccy:
        return amount
    usd = mono.get_exchange(840)
    eur = mono.get_exchange(978)
    if not usd or not eur:
        return None
    rates = {
        'USD': {'buy': usd['rateBuy'], 'sell': usd['rateSell']},
        'EUR': {'buy': eur['rateBuy'], 'sell': eur['rateSell']},
    }
    uah = amount if from_ccy == 'UAH' else amount * rates[from_ccy]['buy']
    return uah if to_ccy == 'UAH' else uah / rates[to_ccy]['sell']


# --- Callback handler ---

@bot.callback_query_handler(func=lambda call: True)
def iq_callback(query):
    bot.answer_callback_query(query.id)
    data = query.data
    chat_id = query.message.chat.id
    msg_id = query.message.message_id

    if data.startswith('get-'):
        ex = mono.get_exchange(int(data[4:]))
        if ex is None:
            bot.send_message(chat_id, 'Exchange rate not found.')
            return
        bot.send_message(chat_id, serialize_ex(ex), parse_mode='HTML')

    elif data.startswith('from-'):
        from_ccy = data[5:]
        state = _convert_state.get(chat_id)
        if not state:
            return
        state['from_ccy'] = from_ccy
        state['step'] = 'to'
        bot.edit_message_text(
            f'Convert from <b>{from_ccy}</b>. Convert to:',
            chat_id, msg_id,
            reply_markup=currency_inline_keyboard('to', exclude=from_ccy),
            parse_mode='HTML'
        )

    elif data.startswith('to-'):
        to_ccy = data[3:]
        state = _convert_state.pop(chat_id, None)
        if not state:
            return
        result = convert_amount(state['amount'], state['from_ccy'], to_ccy)
        if result is None:
            bot.edit_message_text('Could not fetch exchange rates.', chat_id, msg_id)
            return
        bot.edit_message_text(
            f'<b>{state["amount"]:g} {state["from_ccy"]} = {result:.2f} {to_ccy}</b>',
            chat_id, msg_id,
            parse_mode='HTML'
        )

    elif data == 'alert-add':
        bot.edit_message_text(
            'Select currency to watch:',
            chat_id, msg_id,
            reply_markup=alert_ccy_keyboard()
        )

    elif data == 'alert-list':
        alerts = _alerts.get(chat_id, [])
        if not alerts:
            bot.edit_message_text('You have no active alerts.', chat_id, msg_id)
            return
        markup = telebot.types.InlineKeyboardMarkup()
        lines = []
        for i, a in enumerate(alerts):
            lines.append(f'{i + 1}. {a["currency"]}/UAH {a["direction"]} {a["value"]}')
            markup.add(telebot.types.InlineKeyboardButton(f'❌ Delete #{i + 1}', callback_data=f'alert-del-{i}'))
        bot.edit_message_text('\n'.join(lines), chat_id, msg_id, reply_markup=markup)

    elif data.startswith('alert-ccy-'):
        currency = data[10:]
        _alert_state[chat_id] = {'step': 'direction', 'currency': currency}
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton('📈 Above (>)', callback_data='alert-dir->'),
            telebot.types.InlineKeyboardButton('📉 Below (<)', callback_data='alert-dir-<'),
        )
        bot.edit_message_text(
            f'<b>{currency}/UAH</b> — notify when rate is:',
            chat_id, msg_id,
            reply_markup=markup,
            parse_mode='HTML'
        )

    elif data.startswith('alert-dir-'):
        direction = data[10:]
        state = _alert_state.get(chat_id)
        if not state:
            return
        state['direction'] = direction
        state['step'] = 'value'
        bot.edit_message_text(
            f'Enter the threshold for <b>{state["currency"]}/UAH {direction}</b>:',
            chat_id, msg_id,
            parse_mode='HTML'
        )

    elif data.startswith('bestrate-'):
        ccy = data[9:]
        bot.send_chat_action(chat_id, 'typing')
        try:
            results = banks.get_best_rates(ccy)
        except Exception:
            bot.edit_message_text('Could not fetch rates. Try again later.', chat_id, msg_id)
            return
        if not results:
            bot.edit_message_text('No rate data available.', chat_id, msg_id)
            return
        lines = [f'<b>🏦 Cheapest {ccy}/UAH to buy (sell rate)</b>\n']
        for i, r in enumerate(results, 1):
            lines.append(f'{i}. {r["bank"]:15} Buy: {r["buy"]}  Sell: {r["sell"]}')
        bot.edit_message_text('\n'.join(lines), chat_id, msg_id, parse_mode='HTML')

    elif data.startswith('history-'):
        ccy = data[8:]
        try:
            entries = mono.get_nbu_history(ccy)
        except Exception:
            bot.edit_message_text('Could not fetch history. Try again later.', chat_id, msg_id)
            return
        if not entries:
            bot.edit_message_text(f'No history data available for {ccy}/UAH.', chat_id, msg_id)
            return
        lines = [f'<b>📈 {ccy}/UAH — NBU official rate, last 7 days</b>\n']
        for e in entries:
            lines.append(f'{e["date"]}  —  {e["rate"]}')
        bot.edit_message_text('\n'.join(lines), chat_id, msg_id, parse_mode='HTML')

    elif data.startswith('alert-del-'):
        idx = int(data[10:])
        alerts = _alerts.get(chat_id, [])
        if idx < len(alerts):
            removed = alerts.pop(idx)
            bot.edit_message_text(
                f'✅ Deleted: {removed["currency"]}/UAH {removed["direction"]} {removed["value"]}',
                chat_id, msg_id
            )
        else:
            bot.edit_message_text('Alert not found.', chat_id, msg_id)


bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

web.run_app(app, host='0.0.0.0', port=INTERNAL_PORT)
