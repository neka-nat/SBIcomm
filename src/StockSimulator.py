# -*- coding: utf-8 -*-
#!/usr/bin/env python
try:
    import psyco
    psyco.full()
except ImportError:
    pass

import cPickle, datetime
from yahoo_finance_jp import OPEN, CLOSE, MAX, MIN, VOLUME, N_DATA

f = open("data/stock_data.dat", 'r')
print "Loading datum..."
stock_values = cPickle.load(f)
print "Finish loading datum"
f.close()

f = open("data/nikkei_avg.dat", 'r')
print "Loading datum..."
nikkei_avg = cPickle.load(f)
print "Finish loading datum"
f.close()

f = open("data/credit_records.dat", 'r')
print "Loading datum..."
credit_records = cPickle.load(f)
print "Finish loading datum"
f.close()

f = open("data/usdjpy.dat", 'r')
print "Loading datum..."
usdjpy = cPickle.load(f)
print "Finish loading datum"
f.close()

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
    def __init__(self, init_res=500000, use_data=True):
        self.t = 0
        self.w = 0
        self.resource = init_res

        if use_data == True:
            self.stock_values = stock_values
            self.nikkei_avg = nikkei_avg
            self.credit_records = credit_records
            self.usdjpy = usdjpy

        self.buy_orders = {}
        self.sell_orders = {}
        self.order_num = 0

    def buy_order(self, code, num, order=None, stock_values=None):
        if num <= 0:
            return None
        margin = self.get_purchase_margin()
        if stock_values is None:
            stock_values = self.stock_values[self.t][1]
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

    def get_purchase_margin(self, stock_values=None):
        margin = self.resource
        if stock_values is None:
            stock_values = self.stock_values[self.t][1]
        for key, order in self.buy_orders.items():
            if order.ordered == False and order.code in stock_values.keys():
                margin -= stock_values[order.code][CLOSE] * order.num
        return margin

    def get_total_eval(self, stock_values=None):
        total = 0
        if stock_values is None:
            stock_values = self.stock_values[self.t][1]
        for key, order in self.buy_orders.items():
            if order.ordered == True and order.code in stock_values.keys():
                total += stock_values[order.code][OPEN]*order.num
        return total

    def get_value(self, code):
        if code in self.stock_values[self.t][1].keys():
            return self.stock_values[self.t][0], self.stock_values[self.t][1][code]
        else:
            return self.stock_values[self.t][0], None

    def get_nikkei_avg(self):
        return self.nikkei_avg[self.t][1:]

    def get_usdjpy(self):
        return self.usdjpy[self.t][1:]

    def get_credit_record(self, code):
        if code in self.credit_records[self.w][1].keys():
            return self.credit_records[self.w][1][code]
        else:
            return None

    def get_today(self):
        return self.stock_values[self.t][0]

    def step(self, stock_values=None):
        if stock_values is None:
            if self.stock_values[self.t][0] >= self.credit_records[self.w][0] + datetime.timedelta(days=7):
                self.w += 1
            self.t += 1
            stock_values = self.stock_values[self.t][1]

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

    def get_hold_stock_info(self, stock_values=None):
        stock_list = {}
        if stock_values is None:
            stock_values = self.stock_values[self.t][1]
        for key, order in self.buy_orders.items():
            if order.code in stock_values.keys() and order.ordered == True:
                stock_list[order.code] = {"number":order.num,
                                          "value":order.value,
                                          "gain":stock_values[order.code][CLOSE] - order.value}
        return stock_list

    def is_ended(self):
        if self.t >= len(self.stock_values)-1:
            return True
        else:
            return False

    def reset(self):
        self.t = 0
        self.w = 0
