import logging
import os

import telebot
from aiohttp import web

import mono

currencyDict = {840: 'USA', 978: 'EUR', 980: 'UAH'}

API_TOKEN = os.environ.get('TOKEN')
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST', 'exchangebot.duckdns.org')
WEBHOOK_URL = f'https://{WEBHOOK_HOST}/{API_TOKEN}/'
INTERNAL_PORT = int(os.environ.get('PORT', 8080))

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

bot = telebot.TeleBot(API_TOKEN)
app = web.Application()


async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    return web.Response(status=403)


app.router.add_post('/{token}/', handle)


@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        'Greetings! I can show you MonoBank exchange rates.\n'
        'To get the exchange rates press /exchange.\n'
    )


@bot.message_handler(commands=['exchange'])
def message_handler(message):
    bot.send_message(message.chat.id, "Click on the currency of choice:", reply_markup=gen_markup())


def gen_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(telebot.types.InlineKeyboardButton('USD', callback_data='get-840'),
               telebot.types.InlineKeyboardButton('EUR', callback_data='get-978'))
    return markup


def serialize_ex(ex_json):
    return (
        f'<b>{currencyDict[ex_json["currencyCodeB"]]} -> {currencyDict[ex_json["currencyCodeA"]]}:</b>\n\n'
        f'Buy: {ex_json["rateBuy"]}\n\n'
        f'Sell: {ex_json["rateSell"]}'
    )


@bot.callback_query_handler(func=lambda call: True)
def iq_callback(query):
    try:
        bot.answer_callback_query(query.id)
        send_exchange_result(query.message, query.data)
    except ValueError:
        pass


def send_exchange_result(message, ex_code):
    bot.send_chat_action(message.chat.id, 'typing')
    ex = mono.get_exchange(int(ex_code[4:]))
    if ex is None:
        bot.send_message(message.chat.id, 'Exchange rate not found.')
        return
    bot.send_message(message.chat.id, serialize_ex(ex), parse_mode='HTML')


bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

web.run_app(app, host='0.0.0.0', port=INTERNAL_PORT)
