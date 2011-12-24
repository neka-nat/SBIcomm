#!/bin/usr/env python
# -*- coding:utf-8 -*-
import sys, time, datetime, pickle
import traceback
import yaml, workdays
from SBIcomm import *
import StockSimulator
import yahoo_finance_jp, quotes
from yahoo_finance_jp import OPEN, CLOSE, MAX, MIN, VOLUME, N_DATA
from code import CODE
import logging
import logging.config
logging.config.fileConfig('log.conf')
logger = logging.getLogger('trade')

import numpy
from pylab import *
from matplotlib.dates import  DateFormatter, WeekdayLocator, DayLocator, MONDAY, date2num, num2date
from matplotlib.finance import candlestick, plot_day_summary, candlestick2

import ConfigParser
# configファイルの読み込み
conf = ConfigParser.SafeConfigParser()
conf.read('trader.conf')
USERNAME = conf.get('infomation', 'username')
PASSWARD = conf.get('infomation', 'password')

GA_PARAM = [-3.066033838989616, 49.139048308887546, -34.730907381269624, 7.1634582429315055]
def param2rate(param):
    rate_param = [0.0 for _ in range(4)]
    rate_param[0] = param[0]/1000.0 - 0.1
    rate_param[1] = param[1]*100000.0 + 20000000.0
    rate_param[2] = param[2] + 180
    rate_param[3] = param[3]/50.0 + 5
    return rate_param
DOWN_RATE, AVG_VAL, TM, TMS = param2rate(GA_PARAM)

INDICES = ['nk225', 'nk225f', 'topix', 'jasdaq_average',
           'jasdaq_index', 'jasdaq_standard', 'jasdaq_growth',
           'jasdaq_top20', 'j_stock', 'mothers_index', 'jgb_long_future']

def lowpass_filter(tm, value, filt_value):
    """
    ローパスフィルター
    """
    return [(value[i] + tm*filt_value[i])/(1.0+tm) for i in range(len(filt_value))]

def get_stock_data(code, length):
    """
    企業コードと株価履歴を返す
    """
    return (code, yahoo_finance_jp.getTick(code, length=length))

def init_filter(tm_list):
    """
    フィルター値の初期化
    """
    from Pool2 import Pool2
    from functools import partial
    filt_value = [{} for _ in range(len(tm_list))]
    tm_max = max(tm_list)

    p = Pool2(50)
    datum = p.map(partial(get_stock_data, length=int(tm_max)), CODE.values())

    for code, data in datum:
        data.reverse()
        if len(data) > 0:
            for i, tm in enumerate(tm_list):
                filt_value[i][code] = data[0][1:]
                for d in data:
                    filt_value[i][code] = lowpass_filter(tm, d[1:], filt_value[0][code])
    return filt_value

class Order:
    def __init__(self, day, code, value, num):
        self.day = day
        self.code = code
        self.value = value
        self.num = num

class Trader:
    orders = {}
    def __init__(self, init_res, sbi, max_order=5, use_time=OPEN):
        self.resource = init_res
        self.order_num = 0
        self.sbi = sbi
        self.max_order = max_order
        hold_stock = sbi.get_hold_stock_info()
    def buy(self, code, num):
        if len(self.orders) >= self.max_order:
            return False
        day = datetime.date.today()
        value = self.sbi.get_value(code)
        try:
            margin = self.sbi.get_purchase_margin()
            if margin > value[1][CLOSE] * num:
                #order_no = self.sbi.buy_order(code, num, order='MRK_YORI')
                #logger.info("Order NO is %s" % order_no)
                pass
            else:
                return False
        except:
            logger.info("Cannot Buy %d" % code)
            logger.info(traceback.format_exc())
            return False
        self.orders[self.order_num] = Order(day, code, value, num)
        self.order_num += 1
        logger.info("Buy code:%d, value:%d, num:%d" % (code, value, num))
        return True

    def sell(self, order_num):
        if order_num in self.orders: 
            #self.sbi.sell_order(self.orders[order_num].code, self.orders[order_num].num, order='MRK_YORI')
            logger.info("Sell code:%d, num:%d" % (self.orders[order_num].code, self.orders[order_num].num))
            del(self.orders[order_num])
            return True
        else:
            return False

    def get_total_resource(self):
        total_res = self.sbi.get_total_eval() + self.sbi.get_purchase_margin()
        return total_res

class SimTrader:
    orders = {}
    def __init__(self, init_res, sim, max_order=5, use_time=OPEN):
        self.resource = init_res
        self.order_num = 0
        self.sim = sim
        self.max_order = max_order
        self.use_time = use_time

    def buy(self, code, num):
        if len(self.orders) >= self.max_order:
            return False
        if code in self.sim.getNextData():
            stock_value = self.sim.getNextData()[code]
        else:
            return False
        if self.resource > stock_value[self.use_time]*num:
            self.resource -= stock_value[self.use_time]*num
            self.orders[self.order_num] = Order(self.sim.getNowDay(), code, stock_value[self.use_time], num)
            self.order_num += 1
            return True
        else:
            return False

    def sell(self, order_num):
        if order_num in self.orders and self.orders[order_num].code in self.sim.getNextData():
            stock_value = self.sim.getNextData()[self.orders[order_num].code]
            self.resource += stock_value[self.use_time] * self.orders[order_num].num
            del(self.orders[order_num])
            return True
        else:
            return False

    def get_total_resource(self):
        total_res = self.resource
        for order in self.orders.values():
            if order.code in self.sim.getStockValue():
                stock_value = self.sim.getStockValue()[order.code]
                total_res += stock_value[self.use_time] * order.num
            else:
                total_res += order.value * order.num
        return total_res

class TradeManeger:
    STOCK_UNIT = 100
    use_time = CLOSE
    simulate = True

    cnt = 0
    max_down_rate = 1.0

    def __init__(self, username, password, tm_list, simulate=True):
        self.simulate = simulate
        if self.simulate == True:
            self.sbi = StockSimulator.StockSimulator()
            self.sbi.load()
            self.filt_value = [{}, {}]
        else:
            self.sbi = SBIcomm(username, password)
            self.total_res = self.get_total_resource()
            try:
                f = open("filt_value.dat", 'r')
                day, self.filt_value = yaml.load(f)
                f.close()
                if not datetime.date.today() <= workdays.workday(day, 1, holidays_list(day.year)):
                    self.filt_value = init_filter(tm_list)
            except:
                logger.info(traceback.format_exc())
                self.filt_value = init_filter(tm_list)

        if self.simulate == True:
            self.trader = SimTrader(500000, sim=self.sbi)
            self.total_res = self.trader.get_total_resource()
        else:
            self.trader = Trader(self.total_res, self.sbi)
        logger.info("Init Res :%d" % self.total_res)

    def trade(self, down_rate, avg_val, tm, tms):
        today = datetime.date.today()
        # 祝日はトレードできない
        if today in holidays_list(today.year):
            logger.info("Today is holiday! : " + str(today))
            return
        logger.info("****** Start Trading ******")
        stock_value = {}
        for code in CODE.values():
            value = self.sbi.get_value(code)
            if not value[1] is None:
                stock_value[code] = value[1]
            day = value[0]
        for key, data in stock_value.items():
            if key in self.filt_value[0].keys():
                self.filt_value[0][key] = lowpass_filter(tm, data, self.filt_value[0][key])
                self.filt_value[1][key] = lowpass_filter(tms, data, self.filt_value[1][key])
            else:
                self.filt_value[0][key] = data
                self.filt_value[1][key] = data

        if self.simulate == True:
            if self.sbi.t <= tm:
                return
        else:
            # データの保存
            f = open("filt_value.dat", 'w')
            yaml.dump([today, self.filt_value], f)
            f.close()
            f = open("stock_value_%s.dat" % str(day), 'w')
            pickle.dump([day, stock_value], f)
            f.close()
            f = open("market_indices_%s.dat" % str(day), 'w')
            indices = dict((idx, self.sbi.get_market_index(idx)) for idx in INDICES)
            pickle.dump([day, indices], f)
            f.close()
            f = open("quotes_%s.dat" % str(day), 'w')
            pickle.dump([today, quotes.realtime_quotes()], f)
            f.close()
            f = open("market_info_%s.dat" % str(day), 'w')
            pickle.dump([self.sbi.get_market_info(i) for i in range(1,8)], f)
            f.close()
            f = open("market_news_%s.dat" % str(day), 'w')
            pickle.dump(self.sbi.get_market_news(), f)
            f.close()

        # 買い判定
        # 条件を満たすものを検索
        searched_codes = {}
        buy_condition = [lambda key, v:self.filt_value[0][key][self.use_time] < v[self.use_time],
                         lambda key, v:self.filt_value[0][key][VOLUME]*self.filt_value[0][key][self.use_time] > avg_val,
                         lambda key, v:(v[self.use_time] - self.filt_value[1][key][self.use_time])/v[self.use_time] < down_rate]
        for key, v in stock_value.items():
            if all([cnd(key, v) for cnd in buy_condition]):
                searched_codes[key] = v
        if len(searched_codes) > 0:
            for key, v in sorted(searched_codes.items(), key = lambda x: self.filt_value[0][x[0]][VOLUME], reverse=True):
                logger.info("Buy code: %d, num: %d" % (key, self.STOCK_UNIT*5))
                self.trader.buy(key, self.STOCK_UNIT*5)

        # 売り判定
        sell_condition = [lambda order:self.filt_value[0][order.code][self.use_time] > stock_value[order.code][self.use_time],
                          lambda order:(stock_value[order.code][self.use_time] - self.filt_value[1][order.code][self.use_time])/stock_value[order.code][self.use_time] > 0.0]
        for key, order in self.trader.orders.items():
            if order.code in stock_value:
                if all([cnd(order) for cnd in sell_condition]):
                    # 条件合致で全部売る
                    logger.info("Sell code: %d" % key)
                    self.trader.sell(key)
        # Loss Cut
        for key, order in self.trader.orders.items():
            if order.code in stock_value:
                loss = (stock_value[order.code][self.use_time] - order.value)*order.num
                if loss < -self.get_total_resource()*0.05 or day - order.day > datetime.timedelta(days=10):
                    logger.info("Loss Cut code: %d" % key)
                    self.trader.sell(key)
        logger.info("***** End Trading *****")

        # calc down rate
        total_res = self.get_total_resource()
        if self.cnt == 0:
            self.rate_base = total_res
        else:
            if self.max_down_rate > total_res/self.rate_base:
                self.max_down_rate = total_res/self.rate_base
            elif total_res/self.rate_base > 1.0:
                self.rate_base = total_res
        self.cnt += 1

    def get_max_down_rate(self):
        return self.max_down_rate

    def get_total_resource(self):
        if self.simulate == True:
            self.total_res = self.trader.get_total_resource()
        else:
            self.total_res = self.sbi.get_total_eval() + self.sbi.get_purchase_margin()
        logger.info("Res: %d" % self.total_res)
        return self.total_res


def real_trade():
    """
    自動売買
    """
    from apscheduler.scheduler import Scheduler
    import signal

    # Start the scheduler
    sched = Scheduler()
    sched.start()

    maneger = TradeManeger(USERNAME, PASSWARD, [TM, TMS], simulate=False)

    sched.add_cron_job(maneger.trade, day_of_week='mon-fri', hour=7, args=[DOWN_RATE, AVG_VAL, TM, TMS])
    sched.add_cron_job(maneger.get_total_resource, day_of_week='mon-fri', hour=17)
    signal.pause()

def view_data(days, data):
    """
    データのグラフ化
    """
    mondays       = WeekdayLocator(MONDAY)  # major ticks on the mondays
    alldays       = DayLocator()            # minor ticks on the days
    weekFormatter = DateFormatter('%b %d')  # Eg, Jan 12
    dayFormatter  = DateFormatter('%d')     # Eg, 12

    fig = figure()
    fig.subplots_adjust(bottom=0.2)
    ax = fig.add_subplot(111)
    ax.xaxis.set_major_locator(mondays)
    ax.xaxis.set_minor_locator(alldays)
    ax.xaxis.set_major_formatter(weekFormatter)
    ax.plot(days, data)

    ax.xaxis_date()
    ax.autoscale_view()
    setp( gca().get_xticklabels(), rotation=45, horizontalalignment='right')

    #show()
    savefig('graph.png')

def sim_trade(params, graph=True):
    """
    トレードのシミュレーション
    """
    maneger = TradeManeger(USERNAME, PASSWARD, params[2:4])
    days = []
    data = []
    while maneger.sbi.isLastDay() == False:
        maneger.trade(*params)
        days.append(maneger.sbi.getNowDay())
        data.append(maneger.get_total_resource())
        print days[-1], data[-1]
        maneger.sbi.goNextDay()
        evl = float(500000)/data[-1] + 1.0/maneger.get_max_down_rate()
    if graph:
        view_data(days, data)
    return evl

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'sim':
        sim_trade()
    else:
        real_trade()

