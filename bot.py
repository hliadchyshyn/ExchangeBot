# -*- coding: utf-8 -*-
import os

import telebot

import mono


currencyDict = {840: 'USA', 978: 'EUR', 980: 'UAH'}

TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
PORT = int(os.environ.get('PORT', 5000))


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
             'Sell: ' + str(ex_json['rateSell'])
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


bot.start_webhook(listen="0.0.0.0",
                          port=int(PORT),
                          url_path=TOKEN)
bot.setWebhook('https://polar-hamlet-33607.herokuapp.com/' + TOKEN)