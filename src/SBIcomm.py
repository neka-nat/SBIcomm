#!/bin/usr/env python
# -*- coding:utf-8 -*-
import sys, re
import time, datetime, workdays
import mechanize
from BeautifulSoup import BeautifulSoup

import logging
import copy

def set_encode(br, enc):
    """
    サイトのエンコードを変更する
    これをしないとSBI証券ではWindows-31Jを用いているためうまくdecodeできない
    """
    br._factory.encoding = enc
    br._factory._forms_factory.encoding = enc
    br._factory._links_factory._encoding = enc

COMP = {'MORE':'0', 'LESS':'1'}
ORDER = {'LIM_UNC':' ', 'LIM_YORI':'Z', 'LIM_HIKI':'I', 'LIM_HUSE':'F', 'LIM_IOC':'P',
         'MRK_UNC':'N', 'MRK_YORI':'Y', 'MRK_HIKI':'H', 'MRK_IOC':'O'}
CATEGORY = {'SPC':'0', 'STD':'1'}

# 祝日の設定
holidays = []
SLEEP_TIME = 2

class SBIcomm:
    # URL
    DOMAIN = "https://k.sbisec.co.jp"
    STOCK_DIR = DOMAIN + "/bsite/member/stock"
    ACC_DIR = DOMAIN + "/bsite/member/acc"
    pages = {'top':DOMAIN + "/bsite/visitor/top.do",
             'search':DOMAIN + "/bsite/price/search.do",
             'buy':STOCK_DIR + "/buyOrderEntry.do?ipm_product_code=%d&cayen.isStopOrder=%s",
             'sell':STOCK_DIR + "/sellOrderEntry.do?ipm_product_code=%d&cayen.isStopOrder=%s",
             'list':STOCK_DIR + "/orderList.do?cayen.comboOff=1",
             'correct':STOCK_DIR + "/orderCorrectEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_no=%s",
             'cancel':STOCK_DIR + "/orderCancelEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_num=%s",
             'schedule':ACC_DIR + "/stockClearingScheduleList.do",
             'manege':ACC_DIR + "/holdStockList.do"}

    ENC = "cp932"

    logger = logging.getLogger("mechanize")
    logfile = open("sbicomm.log", 'w')
    logger.addHandler(logging.StreamHandler(logfile))
    logger.setLevel(logging.DEBUG)

    pat = re.compile(r'\d+')

    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.br = mechanize.Browser()
        self.br.set_handle_robots(False)

        #self.br.set_debug_http(True)
        #self.br.set_debug_redirects(True)
        #self.br.set_debug_responses(True)

    def __del__(self):
        self.br.close()

    def submit_user_and_pass(self):
        """
        トップページにユーザー名とパスワードを送信
        """
        self.br.open(self.pages['top'])
        set_encode(self.br, self.ENC)
        self.br.select_form(name="form1")
        self.br["username"] = self.username
        self.br["password"] = self.password
        self.br.submit()
        time.sleep(SLEEP_TIME)

    def get_value(self, code):
        """
        現在の日付、株価を返す
        """
        res = self.br.open(self.pages['search'])
        set_encode(self.br, self.ENC)
        self.br.select_form(nr=0)
        self.br["ipm_product_code"] = str(code)
        self.br.submit()
        res = self.br.response()
        # 取得したhtmlを解析して日付と価格を求める
        html = res.read().decode(self.ENC)
        soup = BeautifulSoup(html)
        price_list = soup.findAll("tr", valign="top")
        end_price = float(price_list[2].find("font").contents[0])
        gain_loss = eval(price_list[3].find("font").contents[0])
        m = [re.search(r"\d+", price_list[i].findAll("td", align="right")[0].contents[0]) for i in range(4,7)]
        start_price = float(m[0].group(0))
        max_price = float(m[1].group(0))
        min_price = float(m[2].group(0))
        volume = int("".join(self.pat.findall(price_list[4].findAll("td", align="right")[1].contents[0])))
        # 日付の取得
        num_list = self.pat.findall(price_list[2].findAll("td")[1].contents[1])
        date = datetime.date(datetime.date.today().year, int(num_list[0]), int(num_list[1]))
        return date, [start_price, end_price, max_price, min_price, volume, gain_loss, gain_loss/(end_price-gain_loss)]

    def buy_order(self, code, quantity=None, price=None, limit=0, order='LIM_UNC',
                  comp='MORE', category='SPC', inv=False, trigger_price=None):
        """
        買注文を行う
        """
        self._init_open(self.pages['buy'] % (code, str(inv).lower()))
        self.br.select_form(nr=0)
        self._set_order_propaty(quantity, price, limit, order, comp)
        if inv == True:
            self.br["trigger_price"] = str(trigger_price)
        self.br["hitokutei_trade_kbn"] = [CATEGORY[category]]
        self.br["password"] = self.password
        return self._confirm()

    def sell_order(self, code, quantity=None, price=None, limit=0, order='LIM_UNC',
                   comp='MORE', inv=False, trigger_price=None):
        """
        売注文を行う
        """
        self._init_open(self.pages['sell'] % (code, str(inv).lower()))
        self.br.select_form(nr=0)
        self._set_order_propaty(quantity, price, limit, order, comp)
        if inv == True:
            self.br["trigger_price"] = str(trigger_price)
        self.br["password"] = self.password
        return self._confirm()

    def get_order_num_list(self):
        """
        オーダーのリストを取得する
        """
        soup = self._get_soup(self.pages['list'])
        lists = soup.findAll("td", width="20%", align="center")
        mlist = [re.search("\d{6}", l.findAll("a")[0]['href']) for l in lists]
        return [m.group(0) for m in mlist]

    def get_order_info(self, order_num):
        """
        オーダーの情報を取得する
        """
        soup = self._get_soup(self.pages['correct'] % order_num)
        try:
            l = soup.find("form", action="/bsite/member/stock/orderCorrectEntry.do", method="POST")
            m = re.search("\d{4}", l.find("td").contents[0].contents[0])
            code = int(m.group(0))
            l = soup.find("form", action="/bsite/member/stock/orderCorrectConfirm.do", method="POST")
            state = l.findAll("td")[1].contents[0]
            n_order = int(l.findAll("td")[3].contents[0].rstrip(u"株"))
            return {'code':code, 'number':n_order, 'state':state}
        except:
            raise "Cannot get info!", order_num

    def get_purchase_margin(self, wday_step=0):
        """
        指定した営業日後での買付余力を取得する
        """
        soup = self._get_soup(self.pages['schedule'])
        lists = soup.findAll("tr", bgcolor="#f9f9f9")
        return int("".join(self.pat.findall(lists[wday_step].find("td", align="right").contents[0])))

    def get_total_eval(self):
        """
        現在の評価合計を取得する
        """
        soup = self._get_soup(self.pages['manege'])
        lists = soup.findAll("table", border="0", cellspacing="1", cellpadding="2", width="100%")
        return int("".join(self.pat.findall(lists[0].findAll("td")[1].contents[0])))

    def cancel_order(self, order_num):
        """
        注文のキャンセル
        """
        self._init_open(self.pages['cancel'] % order_num)
        self.br.select_form(nr=0)
        self.br["password"] = self.password
        self.br.submit()

    def _set_order_propaty(self, quantity, price, limit, order, comp):
        """
        オーダー時の設定を行う
        """
        self.br["quantity"] = str(quantity)
        self.br["price"] = str(price)
        if limit == 0:
            self.br["caLiKbn"] = ["today"]
        elif limit <= 6:
            self.br["caLiKbn"] = ["limit"]
            day = workdays.workday(datetime.date.today(), limit, holidays)
            self.br["limit"]=[day.strftime("%Y/%m/%d")]
        else:
            raise "Cannot setting 6 later working day!"
        self.br["sasinari_kbn"] = [ORDER[order]]
        self.br["trigger_zone"] = [COMP[comp]]

    def _confirm(self):
        """
        確認画面での最終処理を行う
        """
        req = self.br.click(type="submit", nr=1)
        res = self.br.open(req)
        set_encode(self.br, self.ENC)
        self.br.select_form(nr=0)
        try:
            req = self.br.click(type="submit", nr=0)
            print "Submitting Order..."
            time.sleep(SLEEP_TIME)
            res = self.br.open(req)
        except:
            raise "Cannot Order!"
        try:
            html = res.read().decode(self.ENC)
            soup = BeautifulSoup(html)
            inputs = soup.findAll("input")
            res.close()
            return inputs[0]["value"]
        except:
            raise "Cannot Get Order Code!"

    def _init_open(self, page):
        """
        ユーザのパスワードを送信してpageをオープンする
        """
        self.submit_user_and_pass()
        res = self.br.open(page)
        set_encode(self.br, self.ENC)

    def _get_soup(self, page):
        """
        指定したページをパースするパーサを取得する
        """
        self.submit_user_and_pass()
        res = self.br.open(page)
        html = res.read().decode(self.ENC)
        return BeautifulSoup(html)

if __name__ == "__main__":
    sbi = SBIcomm("hogehoge", "hogehoge")
    print sbi.buy_order(6758,100,1000, inv=True, trigger_price=999)
    print sbi.get_value(6758)
    print sbi.get_purchase_margin()
    print sbi.get_total_eval()
