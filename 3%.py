from binance.client import Client, BinanceAPIException
import configparser
import re
import time

# Загрузка ключей из файла config
config = configparser.ConfigParser()
config.read_file(open('secret.cfg'))                # Файл с кключами
api_key = config.get('BINANCE', 'API_KEY')          # Логин API бинанса
secret_key = config.get('BINANCE', 'SECRET_KEY')    # Пароль API бинанса
client = Client(api_key, secret_key, testnet=False)

# shopping_list = []                                # Список монет, подходящих для покупки
profit_percent = 3                                  # Процент прироста стоимости монеты, с которого можно её продавать
pattern_USDT = "\w+(?<![UP|DOWN])USDT"                            # Патерн для выбора пар с USDT

all_money = 75                                      # Имеющиеся деньги
available_coins = []                                # Монеты в наличие
recently_sold_coins = []                            # Недавно проданные монеты


# Покупает на ровную сумму все монеты из переданного списка shopping_list, на общую сумму money
# Возвращает список [[купленне монеты, цена покупки, количество монет], ...] и сумму затрат на них
def buy_coins(coins, price_drop_percent):
    global available_coins
    global all_money
    money_to_coin = 25
    for coin in coins:
        coin_price = float(client.get_ticker(symbol=coin)["lastPrice"])
        if money_to_coin > coin_price and all_money > coin_price and all_money > money_to_coin:
            quantity = money_to_coin//coin_price
            all_money -= coin_price * quantity
            available_coins.append([coin, coin_price, quantity, price_drop_percent])


def sell_coins(coins, quantity):
    global all_money
    global available_coins
    profit = 0
    for symbol in coins:
        while True:
            try:
                current_price = float(client.get_ticker(symbol=symbol)["lastPrice"])
                break
            except BinanceAPIException:
                continue
        x = available_coins[:]
        for available_coin in x:
            if available_coin[0] == symbol:
                available_coins.remove(available_coin)
        profit += current_price * quantity
    all_money += profit


def meta_trade(profit_percent, pair_pattern, money):
    pattern = re.compile(pair_pattern)
    if int(time.time())%60 == 0:
        while True:
            try:
                tickers = client.get_ticker()
                break
            except BinanceAPIException:
                continue
        coins_list = sorted(tickers, key=lambda k: k["priceChangePercent"])
        for coin in coins_list:
            pattern_flag = pattern.match(coin["symbol"])
            recently_sold_flag = coin["symbol"] not in recently_sold_coins
            not_available_coin_flag = True
            if available_coins:
                not_available_coin_flag = coin["symbol"] not in list(zip(*available_coins))[0]
            if pattern_flag and recently_sold_flag and not_available_coin_flag:
                while True:
                    try:
                        candles = list(
                            reversed(client.get_klines(symbol=coin["symbol"], interval=client.KLINE_INTERVAL_30MINUTE,
                                                       limit=7)))
                        break
                    except BinanceAPIException:
                        continue
                percent = 0
                for candle in candles:
                    open_price = float(candle[1])
                    close_price = float(candle[4])
                    price_change_percent = (close_price - open_price) / open_price * 100
                    percent += price_change_percent
                if percent < -3:
                    last_candle = float(candles[0][4]) > float(candles[0][1])
                    pre_last_candle = float(candles[1][4]) > float(candles[1][1])
                    prepre_last_candle = float(candles[2][4]) > float(candles[2][1])
                    if last_candle and pre_last_candle and prepre_last_candle:
                        print("Надо брать " + coin["symbol"])
                        buy_coins([coin["symbol"]], percent)


    for coin in available_coins:
        symbol = coin[0]
        purchase_price = coin[1]
        quantity = coin[2]
        price_drop_percent = coin[3]
        current_price = float(client.get_ticker(symbol=coin[0])["lastPrice"])
        price_increase = (current_price - purchase_price) / purchase_price * 100
        if price_increase >= price_drop_percent/-3:
            sell_coins([symbol], quantity)
            recently_sold_coins.append([symbol, int(time.time())])


def menage_recently_sold_coins(coins):
    now = time.time()
    x = coins[:]
    for coin in x:
        if now - coin[1] > 3*60*60:
            coins.remove(coin)


while 1:
    meta_trade(profit_percent, pattern_USDT, all_money)
    menage_recently_sold_coins(recently_sold_coins)
    balance = 0
    for coin in available_coins:
        symbol = coin[0]
        quantity = coin[2]
        balance += float(client.get_ticker(symbol=symbol)['lastPrice']) * quantity

    if int(time.time())%60 == 0:
        print(all_money)
        print(available_coins)
        print(balance + all_money)


