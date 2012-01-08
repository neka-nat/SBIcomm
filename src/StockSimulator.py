# -*- coding: utf-8 -*-
#!/usr/bin/env python

import pickle
import code
from yahoo_finance_jp import OPEN, CLOSE, MAX, MIN, VOLUME, N_DATA

class StockSimulator:
    def __init__(self, data = None):
        self.t = 0
        self.w = 0
        if not data is None:
            self.stock_values = data

    def load(self, filedir="./"):
        f = open("stock_data.dat", 'r')
        print "Loading datum..."
        self.stock_values = pickle.load(f)
        print "Finish loading datum"
        f.close()

        f = open("nikkei_avg.dat", 'r')
        print "Loading datum..."
        self.nikkei_avg = pickle.load(f)
        print "Finish loading datum"
        f.close()

        f = open("credit_records.dat", 'r')
        print "Loading datum..."
        self.credit_records = pickle.load(f)
        print "Finish loading datum"
        f.close()

    def reset(self):
        self.t = 0

    def goNextDay(self):
        self.t += 1
        if self.stock_values[self.t][0] >= self.credit_records[self.w+1][0]:
            self.w += 1

    def get_value(self, code):
        if code in self.stock_values[self.t][1]:
            return self.stock_values[self.t][0], self.stock_values[self.t][1][code]
        else:
            return self.stock_values[self.t][0], None

    def getStockValue(self):
        return self.stock_values[self.t][1]

    def get_credit_record(self, code):
        if code in self.credit_records[self.w][1]:
            credit_records = self.credit_records[self.w][1][code]
            ret = {}
            ret["unsold"] = [credit_records[0], credit_records[2]]
            ret["margin"] = [credit_records[1], credit_records[3]]
            ret["ratio"] = credit_records[4]
            return ret
        else:
            return None

    def getNowDay(self):
        return self.stock_values[self.t][0]

    def getTomorrow(self):
        return self.stock_values[self.t+1][0]

    def getNextData(self):
        return self.stock_values[self.t+1][1]

    def getLastData(self):
        return self.stock_values[-1][1]

    def isLastDay(self):
        if self.t >= len(self.stock_values)-1:
            return True
        else:
            return False

class OrderInfo:
    def __init__(self, code, num, value=None, ordered=False):
        self.code = code
        self.num = num
        self.value = value
        self.ordered = ordered

class BrokerSimulator:
    """
    証券会社のシミュレータ
    """
    def __init__(self, init_res=500000):
        self.resource = init_res
        self.stock_sim = StockSimulator()
        self.stock_sim.load()
        self.buy_orders = {}
        self.sell_orders = {}
        self.order_num = 0

    def buy_order(self, code, num, order=None):
        if num <= 0:
            return None
        margin = self.get_purchase_margin()
        stock_values = self.stock_sim.getStockValue()
        if code in stock_values.keys() and margin > stock_values[code][CLOSE]*num:
            self.buy_orders[self.order_num] = OrderInfo(code, num, stock_values[code][CLOSE])
            self.order_num += 1
            return self.order_num - 1
        else:
            return None
        
    def sell_order(self, code, num, order=None):
        for bkey, border in self.buy_orders.items():
            if border.code == code and border.num >= num and border.ordered == True:
                self.sell_orders[self.order_num] = OrderInfo(code, num)
                self.buy_orders[bkey].num -= num
                self.order_num += 1
                return self.order_num - 1
        return None

    def get_purchase_margin(self):
        margin = self.resource
        stock_values = self.stock_sim.getStockValue()
        for key, order in self.buy_orders.items():
            if order.ordered == False and order.code in stock_values.keys():
                margin -= stock_values[order.code][CLOSE] * order.num
        return margin

    def get_total_eval(self):
        total = 0
        stock_values = self.stock_sim.getStockValue()
        for key, order in self.buy_orders.items():
            if order.ordered == True and order.code in stock_values.keys():
                total += stock_values[order.code][OPEN]*order.num
        return total

    def get_value(self, code):
        return self.stock_sim.get_value(code)

    def get_nikkei_avg(self):
        return self.stock_sim.nikkei_avg[self.stock_sim.t][1:5]

    def get_credit_record(self, code):
        return self.stock_sim.get_credit_record(code)

    def step(self):
        self.stock_sim.goNextDay()
        stock_values = self.stock_sim.getStockValue()

        print "margin:", self.resource

        # 買いオーダーの処理
        for key, order in self.buy_orders.items():
            print "buy:", key, order.code, order.num, order.ordered
            if order.ordered == False:
                if order.code in stock_values.keys() and self.resource > stock_values[order.code][OPEN]*order.num:
                    self.resource -= stock_values[order.code][OPEN]*order.num
                    self.buy_orders[key].ordered = True
                    # かぶっている銘柄をまとめておく
                    for bkey, border in self.buy_orders.items():
                        if bkey != key and border.code == order.code and border.ordered == True:
                            self.buy_orders[bkey].num += order.num
                            self.buy_orders[bkey].value = (border.num*border.value + order.num*order.value)/(border.num+order.num)
                            del(self.buy_orders[key])
                else:
                    # 買えない場合は注文は無効になる
                    del(self.buy_orders[key])

        # 売りオーダーの処理
        for skey, sorder in self.sell_orders.items():
            print "sell:", skey, sorder.code, sorder.num, sorder.ordered
            if sorder.ordered == False:
                if sorder.code in stock_values.keys():
                    self.resource += stock_values[sorder.code][OPEN]*sorder.num
                    self.sell_orders[skey].ordered = True

                    for bkey, border in self.buy_orders.items():
                        if self.buy_orders[bkey].num == 0:
                            del(self.buy_orders[bkey])
                    del(self.sell_orders[skey])

    def get_hold_stock_info(self):
        stock_list = {}
        stock_values = self.stock_sim.getStockValue()
        for key, order in self.buy_orders.items():
            if order.code in stock_values.keys() and order.ordered == True:
                stock_list[order.code] = {"number":order.num,
                                          "value":order.value,
                                          "gain":stock_values[order.code][CLOSE] - order.value}
        return stock_list


    def is_ended(self):
        return self.stock_sim.isLastDay()

    def reset(self):
        self.stock_sim.reset()
