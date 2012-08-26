#!/bin/usr/env python
# -*- coding:utf-8 -*-

import sys, time, datetime, cPickle, traceback
import yaml, workdays
from SBIcomm import *
from code import CODE
import logging
import logging.config
logging.config.fileConfig('log.conf')
logger = logging.getLogger('trade')

import ConfigParser
# configファイルの読み込み
conf = ConfigParser.SafeConfigParser()
conf.read('trader.conf')
USERNAME = conf.get('infomation', 'username')
PASSWARD = conf.get('infomation', 'password')

class DataLogger:
    """
    平日の定時刻にマーケットのデータを取得し保存するクラス
    """
    def __init__(self, username, password, save_dir="data/"):
        self.sbi = SBIcomm(username, password)
        self.save_dir = save_dir
        self.credit_records = {}

    def logging(self):
        today = datetime.date.today()
        # 祝日はトレードできない
        if today in holidays_list(today.year):
            logger.info("Today is holiday! : " + str(today))
            return

        stock_value = {}
        for code in CODE.values():
            value = self.sbi.get_value(code)
            if not value[1] is None:
                stock_value[code] = value[1]
            day = value[0]

        # 信用取引関連のデータを週に一度取得する
        if len(self.credit_records) == 0 or \
                (day.weekday() > workdays.workday(day, 1, holidays_list(day.year)).weekday()):
            for code in CODE.values():
                rec = self.sbi.get_credit_record(code)
                if not rec is None:
                    self.credit_records[code] = rec

            f = open("%scredit_records_%s.dat" % (self.save_dir, str(day)), 'w')
            cPickle.dump(self.credit_records, f)
            f.close()

        # データの保存
        self.data_save(day, stock_value)

    def data_save(self, day, stock_value):
        f = open("%sstock_value_%s.dat" % (self.save_dir, str(day)), 'w')
        cPickle.dump([day, stock_value], f)
        f.close()
        f = open("%smarket_indices_%s.dat" % (self.save_dir, str(day)), 'w')
        indices = dict((idx, self.sbi.get_market_index(idx)) for idx in MARKET_INDICES)
        cPickle.dump([day, indices], f)
        f.close()
        f = open("%smarket_info_%s.dat" % (self.save_dir, str(day)), 'w')
        cPickle.dump([self.sbi.get_market_info(i) for i in range(1,8)], f)
        f.close()
        f = open("%smarket_news_%s.dat" % (self.save_dir, str(day)), 'w')
        cPickle.dump(self.sbi.get_market_news(), f)
        f.close()

def logging_main():
    from apscheduler.scheduler import Scheduler
    import signal

    # Start the scheduler
    sched = Scheduler()
    sched.start()

    maneger = DataLogger(USERNAME, PASSWARD)

    sched.add_cron_job(maneger.logging, day_of_week='mon-fri', hour=7)
    signal.pause()

if __name__ == "__main__":
    logging_main()
