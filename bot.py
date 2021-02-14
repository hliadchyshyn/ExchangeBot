# -*- coding: utf-8 -*-
import os

import telebot

import mono

import logging
import ssl

from aiohttp import web

currencyDict = {840: 'USA', 978: 'EUR', 980: 'UAH'}

API_TOKEN = os.environ.get('TOKEN')

WEBHOOK_HOST = '142.93.234.46'
WEBHOOK_PORT = 8443  # 443, 80, 88 or 8443 (port need to be 'open')
WEBHOOK_LISTEN = '0.0.0.0'  # In some VPS you may need to put here the IP addr

WEBHOOK_SSL_CERT = './webhook_cert.pem'  # Path to the ssl certificate
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'  # Path to the ssl private key

# Quick'n'dirty SSL certificate generation:
#
# openssl genrsa -out webhook_pkey.pem 2048
# openssl req -new -x509 -days 3650 -key webhook_pkey.pem -out webhook_cert.pem
#
# When asked for "Common Name (e.g. server FQDN or YOUR name)" you should reply
# with the same value in you put in WEBHOOK_HOST

WEBHOOK_URL_BASE = "https://{}:{}".format(WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/{}/".format(API_TOKEN)

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

bot = telebot.TeleBot(API_TOKEN)
app = web.Application()


# Process webhook calls
async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)


app.router.add_post('/{token}/', handle)


# msg handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        'Greetings! I can show you MonoBank exchange rates.\n' +
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
    result = '<b>' + str(currencyDict[ex_json['currencyCodeB']]) + ' -> ' \
             + str(currencyDict[ex_json['currencyCodeA']]) + ':</b>\n\n' \
                                                             'Buy: ' + str(ex_json['rateBuy']) + '\n\n' \
                                                                                                 'Sell: ' + str(
        ex_json['rateSell'])
    return result


@bot.callback_query_handler(func=lambda call: True)
def iq_callback(query):
    data = query.data
    try:
        get_ex_callback(query)
    except ValueError:
        pass


def get_ex_callback(query):
    bot.answer_callback_query(query.id)
    send_exchange_result(query.message, query.data)


def send_exchange_result(message, ex_code):
    bot.send_chat_action(message.chat.id, 'typing')
    ex = mono.get_exchange(int(ex_code[4:]))
    result = serialize_ex(ex)
    bot.send_message(
        message.chat.id,
        result,
        parse_mode='HTML')


# Remove webhook, it fails sometimes the set if there is a previous webhook
bot.remove_webhook()

# Set webhook
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
                certificate=open(WEBHOOK_SSL_CERT, 'r'))

# Build ssl context
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

# Start aiohttp server
web.run_app(
    app,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    ssl_context=context,
)
