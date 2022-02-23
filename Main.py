from binance.client import Client
# import configparser
import Trade_machine as trade_machine
from telegram import ChatAction, ReplyKeyboardMarkup, ReplyKeyboardRemove,\
    InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResult
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters,\
    ConversationHandler, CallbackQueryHandler
import logging
import os


# Ключи
bot_token = os.environ['BOT_TOKEN']
api_key = os.environ['API_KEY']
secret_key = os.environ['SECRET_KEY']
PORT = int(os.environ.get('PORT', '8443'))

# Настройка логи
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


# Загрузка ключей из файла config
# config = configparser.ConfigParser()
# config.read_file(open('secret.cfg'))
# api_key = config.get('BINANCE', 'API_KEY')
# secret_key = config.get('BINANCE', 'SECRET_KEY')
client = Client(api_key, secret_key)

machine_name = ''
target_percent = 0
profit_percent = 0
available_money = 0
traders = {}
chat_id = ''

# Статусы диалога
CREATE, NAME, TARGET_PERCENT, PROFIT_PERCENT, MONEY = range(5)


def start_command(update, context):
    keyboard = [[InlineKeyboardButton(text="Создать машину", callback_data="create_machine")]]
    if traders:
        keyboard.append([InlineKeyboardButton(text="Состояние машины", callback_data="states")])
        keyboard.append([InlineKeyboardButton(text="Удалить машину", callback_data="del_machine")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text="Привет", reply_markup=reply_markup)


def create_machine_button(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Задайте имя новой машине')
    return NAME


def set_name_to_machine(update, context):
    global machine_name
    machine_name = update.message.text
    context.bot.send_message(chat_id=update.message.chat_id,
                             text='Задайте значение целового процента падения цены со знаком минус (пример: -9).')
    return TARGET_PERCENT


def set_target_percent(update, context):
    global target_percent
    target_percent = update.message.text
    context.bot.send_message(chat_id=update.message.chat_id,
                             text='Задайте значение целового процента повышения цены (пример: 3).')
    return PROFIT_PERCENT


def set_profit_percent(update, context):
    global profit_percent
    profit_percent = update.message.text

    context.bot.send_message(chat_id=update.message.chat_id,
                             text='Задайте количество доступных денег для машины (пример: 75)')
    return MONEY


def set_available_money(update, context):
    global available_money
    global chat_id
    available_money = update.message.text
    traders[machine_name] = trade_machine.TradeMachine(client, target_percent, profit_percent, available_money)
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id=update.message.chat_id,
                             text='Отлично, ваша машина создана')
    return ConversationHandler.END


def cancel_button(update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
                             text='Операция отменена')
    return ConversationHandler.END


def state_button(update, context):
    keyboard = [[InlineKeyboardButton(text=key, callback_data="state_" + key)] for key in traders]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                          message_id=update.callback_query.message.message_id,
                                          reply_markup=reply_markup)


def del_machine_button(update, context):
    keyboard = [[InlineKeyboardButton(text=key, callback_data="del_" + key)] for key in traders]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                          message_id=update.callback_query.message.message_id,
                                          reply_markup=reply_markup)


def del_machine(update, context):
    trader = update.callback_query.data[4:]
    del traders[trader]
    context.bot.delete_message(chat_id=update.effective_chat.id,
                               message_id=update.callback_query.message.message_id)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f'Ваша машина "{trader}" удалена')


def state(update, context):
    trader = traders[update.callback_query.data[6:]]
    available_coins = trader.available_coins
    available_money = trader.available_money
    price_change_percent_target = trader.price_change_percent_target
    profit_percent = trader.profit_percent
    balance = 0
    for coin in trader.available_coins:
        symbol = coin[0]
        quantity = coin[2]
        balance += float(client.get_ticker(symbol=symbol)['lastPrice']) * quantity
    balance += available_money
    message = f"Целевое падение процента: {price_change_percent_target}\n"\
              f"Процент прибыли: {profit_percent}\n"\
              f"Монеты в наличие: {available_coins}\n" \
              f"Доллары: {available_money}\n" \
              f"Общий баланс: {balance}"
    context.bot.delete_message(chat_id=update.effective_chat.id,
                               message_id=update.callback_query.message.message_id)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message)


def shop(context):
    for key in traders:
        shopping_list = traders[key].get_shopping_list()
        if shopping_list:
            traders[key].buy_coins(shopping_list)
            context.bot.send_message(chat_id=chat_id,
                             text=f"{key} говорит надо брать: {shopping_list}")


def sale(context):
    for key in traders:
        sales_list = traders[key].get_sales_list()
        if sales_list:
            traders[key].sell_coins(sales_list)


def main():
    updater = Updater(token=bot_token, use_context=True)
    dispatcher = updater.dispatcher
    print("Bot is running")

    # Слушатели
    dispatcher.add_handler(CommandHandler(callback=start_command, command="start"))
    dispatcher.add_handler(CallbackQueryHandler(callback=state_button, pattern='states'))
    dispatcher.add_handler(CallbackQueryHandler(callback=del_machine_button, pattern='del_machine'))
    dispatcher.add_handler(CallbackQueryHandler(callback=state, pattern='state_\w+'))
    dispatcher.add_handler(CallbackQueryHandler(callback=del_machine, pattern='del_\w+'))
    dispatcher.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(callback=create_machine_button, pattern='create_machine')],
        states={
            CREATE: [MessageHandler(Filters.text, create_machine_button)],
            NAME: [MessageHandler(Filters.text, set_name_to_machine)],
            TARGET_PERCENT: [MessageHandler(Filters.text, set_target_percent)],
            PROFIT_PERCENT: [MessageHandler(Filters.text, set_profit_percent)],
            MONEY: [MessageHandler(Filters.text, set_available_money)]},
        fallbacks=[CommandHandler('cancel', cancel_button)]))

    shoping = updater.job_queue
    shoping.run_repeating(callback=shop, interval=60)
    saling = updater.job_queue
    saling.run_repeating(callback=sale, interval=30)


    # Начало поиска обновлений
    # updater.start_polling(clean=True)
    updater.bot.set_webhook("https://binancemachine.herokuapp.com/" + bot_token)
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=bot_token)
    # Останавка бота, если были нажаты Ctrl + C
    updater.idle()


if __name__ == '__main__':
    main()

