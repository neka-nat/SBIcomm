#!/bin/usr/env python
# -*- coding:utf-8 -*-
import time, datetime
import codecs, ConfigParser
import pickle
import SBIcomm
from code import CODE
import logging
import logging.config

logging.config.fileConfig('log.conf')
logger = logging.getLogger('top.mid')
result = open("result.txt", "w")
result = codecs.lookup('utf_8')[-1](result)

# configファイルの読み込み
conf = ConfigParser.SafeConfigParser()
conf.read('trader.conf')

USERNAME = conf.get('infomation', 'username')
PASSWARD = conf.get('infomation', 'password')
SAMPLING = int(conf.get('options', 'sampling'))
SIMULATOR = conf.get('options', 'simulator')

if SIMULATOR == "False":
  from SimPy.SimulationRT import *
elif SIMULATOR == "True":
  from SimPy.Simulation import *

today = datetime.date.today()
# 取引開始時刻
start_time = datetime.datetime.combine(today, datetime.time(9, 0, 0))
# 取引終了時刻
end_time = datetime.datetime.combine(today, datetime.time(15, 0, 0))

def unix_time(d):
  """
  datetimeをunixtimeに変換
  """
  return time.mktime(d.timetuple())

class StockTrader(Process):
  def __init__(self,name):
    Process.__init__(self,name=name)
    self.sbi = SBIcomm.SBIcomm(USERNAME, PASSWARD)
    self.init_process()

  def _trade(self):
    logger.debug("Trading Start!")
    stock_data = self.get_all_stock_data()
    pickle.dump((datetime.datetime.now(), stock_data), result)
    logger.debug("Trading End!")

  def init_process(self):
    """
    最初に行うプロセス
    """
    logger.debug("Init Process Start!")
    stock_data = self.get_all_stock_data()
    self.total_eval = self.sbi.get_total_eval()
    self.margin = self.sbi.get_purchase_margin()
    logger.debug("total eval, margin:%f %f" % (self.total_eval, self.margin))

  def get_all_stock_data(self):
    """
    株価を前日比が高い順にソートして返す
    """
    stock_data = {}
    for code in CODE.values():
      value = self.sbi.get_value(code)
      if not value[0] is None:
        stock_data[code] = value
    return stock_data

  def sort_stock_data(self, data):
    return sorted(data.items(), lambda x,y : cmp(x[1][1][6], y[1][1][6]))

  def calc_num_purchase(self, code):
    """
    現在の買付余力で買える最大株数を求める(100株単位)
    """
    day, stock_info = self.sbi.get_value(code)
    return int(self.margin/(stock_info[1]*100))*100

  def process(self):
    logger.debug("Start Trading Process... ")
    while True:
      trade_start = time.time()
      # トレードの開始
      self._trade()
      trade_end = time.time()
      yield hold, self, SAMPLING - (trade_end - trade_start)

if __name__ == "__main__":
  initialize()
  p  = StockTrader("StockTrader")
  boot_time = datetime.datetime.now()
  logger.debug("Program Start!")
  if boot_time > end_time:
    # 15時以降なら実行しない
    logger.debug("Today's trade is end!")
    sys.exit()

  span = unix_time(end_time) - unix_time(boot_time)
  logger.debug("Wait Time %f s" % max([unix_time(start_time) - unix_time(boot_time), 0.0]))
  activate(p, p.process(), at = max([unix_time(start_time) - unix_time(boot_time), 0.0]))
  if SIMULATOR == "False":
    simulate(real_time=True, rel_speed=1, until=span)
  elif SIMULATOR == "True":
    simulate(until=span)
  logger.debug("End Trading...")
  result.close()
