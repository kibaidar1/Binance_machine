from binance.client import BinanceAPIException
from time import time
import re


class TradeMachine:

    def __init__(self, client, price_change_percent_target, profit_percent, available_money):
        self.client = client                                                                    # клиент Бинанса client = Client(api_key, secret_key)
        self.price_change_percent_target = float(price_change_percent_target)                   # % на который должна упасть монета для её покупки
        self.profit_percent = float(profit_percent)                                             # Процент прироста стоимости монеты, с которого можно её продавать
        self.pattern_USDT = re.compile("\w+(?<![UP|DOWN])USDT")                                 # Патерн для выбора пар с USDT
        self.available_money = float(available_money)                                           # Имеющиеся деньги
        self.available_coins = []                                                               # Монеты в наличие
        self.recently_sold_coins = []                                                           # Недавно проданные монеты

    def manage_recently_sold_coins(self):                                                       # Управление списком недавно проданных монет
        x = self.recently_sold_coins[:]
        for coin in x:
            if time() - coin[1] > 3 * 60 * 60:
                self.recently_sold_coins.remove(coin)

    def get_shopping_list(self, update_sec=60):                                                 # Получение списка к покупке монет
        self.manage_recently_sold_coins()
        shopping_list = []
        while True:
            try:
                tickers = self.client.get_ticker()
                break
            except BinanceAPIException:
                continue
        coins_list = sorted(tickers, key=lambda k: k["priceChangePercent"])
        for coin in coins_list:
            pattern_flag = self.pattern_USDT.match(coin["symbol"])
            recently_sold_flag = coin["symbol"] not in self.recently_sold_coins
            not_available_coin_flag = True
            if self.available_coins:
                not_available_coin_flag = coin["symbol"] not in list(zip(*self.available_coins))[0]
            if pattern_flag and recently_sold_flag and not_available_coin_flag:
                while True:
                    try:
                        candles = list(
                            reversed(
                                self.client.get_klines(symbol=coin["symbol"], interval=self.client.KLINE_INTERVAL_30MINUTE,
                                                       limit=10)))
                        break
                    except BinanceAPIException:
                        continue
                drop_percent = 0
                for candle in candles:
                    open_price = float(candle[1])
                    close_price = float(candle[4])
                    price_change_percent = (close_price - open_price) / open_price * 100
                    drop_percent += price_change_percent
                    if drop_percent < self.price_change_percent_target:
                        last_candle = float(candles[0][4]) > float(candles[0][1])
                        pre_last_candle = float(candles[1][4]) > float(candles[1][1])
                        prepre_last_candle = float(candles[2][4]) > float(candles[2][1])
                        if last_candle and pre_last_candle and prepre_last_candle:
                            shopping_list.append(coin["symbol"])
                        break
        return shopping_list

    def get_sales_list(self):                                                                         # Получение списка к продаже монет
        sales_list = []
        for coin in self.available_coins:
            symbol = coin[0]
            purchase_price = coin[1]
            current_price = float(self.client.get_ticker(symbol=coin[0])["lastPrice"])
            price_increase = (current_price - purchase_price) / purchase_price * 100
            if price_increase >= self.profit_percent:
                sales_list.append(symbol)
                self.recently_sold_coins.append([symbol, int(time())])

    def buy_coins(self, coins):                                                                        # Покупка монет по списку
        if len(coins) > 2:
            money_to_coin = self.available_money/len(coins)
        else:
            money_to_coin = self.available_money/3
        for coin in coins:
            coin_price = float(self.client.get_ticker(symbol=coin)["lastPrice"])
            if money_to_coin > coin_price and self.available_money > coin_price and self.available_money > money_to_coin:
                try:
                    quantity = money_to_coin // coin_price
                    self.available_money -= coin_price * quantity
                    self.available_coins.append([coin, coin_price, quantity])
                except ZeroDivisionError:
                    print([coin, coin_price])

    def sell_coins(self, coins):                                                                        # Продажа монет по списку
        for coin_to_sell in coins:
            while True:
                try:
                    current_price = float(self.client.get_ticker(symbol=coin)["lastPrice"])
                    break
                except BinanceAPIException:
                    continue
            x = self.available_coins[:]
            for available_coin in x:
                coin = available_coin[0]
                quantity = available_coin[2]
                if coin == coin_to_sell:
                    self.available_coins.remove(available_coin)
        self.available_money += current_price * quantity

