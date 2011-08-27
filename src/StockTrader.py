#!/bin/usr/env python
# -*- coding:utf-8 -*-
import time, datetime
import ConfigParser
import SBIcomm
import logging
import logging.config

logging.config.fileConfig('log.conf')
logger = logging.getLogger("app")

CODE = {'SONY':6758,
        'TOYOTA':7203,
        'PANA':6752}

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
    self._init_trade()

  def _init_trade(self):
    pass

  def _trade(self):
    print "Now Trading..."
    print self.sbi.get_value(CODE['PANA'])

  def process(self):
    print "Start Trading...", datetime.datetime.now()
    while True:
      trade_start = time.time()
      print datetime.datetime.now(), self.name
      self._trade()
      trade_end = time.time()
      yield hold, self, SAMPLING - (trade_end - trade_start)

if __name__ == "__main__":
  initialize()
  p  = StockTrader("StockTrader")
  boot_time = datetime.datetime.now()
  print "Program Start: ", boot_time
  if boot_time > end_time:
    # 15時以降なら実行しない
    sys.exit("Today's trade is end.")

  span = unix_time(end_time) - unix_time(boot_time)
  activate(p, p.process(), at = max([unix_time(start_time) - unix_time(boot_time), 0.0]))
  if SIMULATOR == "False":
    simulate(real_time=True, rel_speed=1, until=span)
  elif SIMULATOR == "True":
    simulate(until=span)
  print 'End Trading...', datetime.datetime.now()
