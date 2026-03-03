import logging
import os

import telebot
from aiohttp import web

import mono

currencyDict = {840: 'USD', 978: 'EUR', 980: 'UAH'}

API_TOKEN = os.environ.get('TOKEN')
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST', 'exchangebot.duckdns.org')
WEBHOOK_URL = f'https://{WEBHOOK_HOST}/{API_TOKEN}/'
INTERNAL_PORT = int(os.environ.get('PORT', 8080))

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

bot = telebot.TeleBot(API_TOKEN)
app = web.Application()

_convert_state: dict = {}  # {chat_id: {'step': str, 'amount': float, 'from_ccy': str}}


async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    return web.Response(status=403)


app.router.add_post('/{token}/', handle)


def main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('💱 Exchange', '📊 Rates')
    markup.row('🔄 Convert')
    return markup


def currency_inline_keyboard(callback_prefix: str, exclude: str = None):
    markup = telebot.types.InlineKeyboardMarkup()
    buttons = [
        telebot.types.InlineKeyboardButton(c, callback_data=f'{callback_prefix}-{c}')
        for c in ('UAH', 'USD', 'EUR') if c != exclude
    ]
    markup.add(*buttons)
    return markup


@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        'Greetings! I can show you MonoBank exchange rates.',
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
    usd = mono.get_exchange(840)
    eur = mono.get_exchange(978)
    lines = []
    if usd:
        lines.append(f'<b>USD / UAH</b>\nBuy: {usd["rateBuy"]} | Sell: {usd["rateSell"]}')
    if eur:
        lines.append(f'<b>EUR / UAH</b>\nBuy: {eur["rateBuy"]} | Sell: {eur["rateSell"]}')
    bot.send_message(message.chat.id, '\n\n'.join(lines) or 'No data.', parse_mode='HTML')


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


@bot.callback_query_handler(func=lambda call: True)
def iq_callback(query):
    bot.answer_callback_query(query.id)
    data = query.data
    chat_id = query.message.chat.id

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
            chat_id, query.message.message_id,
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
            bot.edit_message_text('Could not fetch exchange rates.', chat_id, query.message.message_id)
            return
        bot.edit_message_text(
            f'<b>{state["amount"]:g} {state["from_ccy"]} = {result:.2f} {to_ccy}</b>',
            chat_id, query.message.message_id,
            parse_mode='HTML'
        )


bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

web.run_app(app, host='0.0.0.0', port=INTERNAL_PORT)
