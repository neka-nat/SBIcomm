#!/bin/usr/env python
# -*- coding:utf-8 -*-
import sys, re
import time, datetime, workdays
import mechanize
from BeautifulSoup import BeautifulSoup

import logging

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

class SBIcomm:
    # URL
    DOMAIN = "https://k.sbisec.co.jp"
    STOCK_DIR = DOMAIN + "/bsite/member/stock"
    ACC_DIR = DOMAIN + "/bsite/member/acc"
    pages = {'top':DOMAIN + "/bsite/visitor/top.do",
             'search':DOMAIN + "/bsite/price/search.do",
             'buy':STOCK_DIR + "/buyOrderEntry.do?ipm_product_code=",
             'sell':STOCK_DIR + "/sellOrderEntry.do?ipm_product_code=",
             'list':STOCK_DIR + "/orderList.do?cayen.comboOff=1",
             'correct':STOCK_DIR + "/orderCorrectEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_no=",
             'cancel':STOCK_DIR + "/orderCancelEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_num=",
             'schedule':ACC_DIR + "/stockClearingScheduleList.do",
             'inv':"&cayen.isStopOrder=true"}

    ENC = "cp932"

    logger = logging.getLogger("mechanize")
    logfile = open("sbicomm.log", 'w')
    logger.addHandler(logging.StreamHandler(logfile))
    logger.setLevel(logging.DEBUG)

    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.br = mechanize.Browser()
        self.br.set_handle_robots(False)
        
        self.br.set_debug_http(True)
        self.br.set_debug_redirects(True)
        self.br.set_debug_responses(True)

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

    def get_prices(self, code):
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
        soup = BeautifulSoup(res.read().decode(self.ENC))
        price_list = soup.findAll("tr", valign="top")
        end_price = float(price_list[2].find("font").contents[0])
        m = [re.search(r"\d+", price_list[i].findAll("td", align="right")[0].contents[0]) for i in range(4,7)]
        start_price = float(m[0].group(0))
        max_price = float(m[1].group(0))
        min_price = float(m[2].group(0))
        volume = int(re.sub(",", "", price_list[4].findAll("td", align="right")[1].contents[0].rstrip(u'株')))
        # 日付の取得
        m = re.search(r"\d{2}/\d{2}", price_list[2].findAll("td")[1].contents[1])
        date = datetime.date(datetime.date.today().year, int(m.group(0)[0:2]), int(m.group(0)[4:6]))
        return date, [start_price, end_price, max_price, min_price, volume]

    def buy_order(self, code, quantity=None, price=None, 
                  limit=0, order='LIM_UNC', comp='MORE', category='SPC'):
        """
        買注文を行う
        """
        self.submit_user_and_pass()
        res = self.br.open(self.pages['buy']+str(code))
        set_encode(self.br, self.ENC)
        self.br.select_form(nr=0)
        self._set_order_propaty(quantity, price, limit, date, order, comp)
        self.br["hitokutei_trade_kbn"] = [CATEGORY[category]]
        self.br["password"] = self.password
        return self._confirm()

    def inv_buy_order(self, code, quantity=None, trigger_price=None, price=None, 
                      limit=0, order='LIM_UNC', comp='MORE', category='SPC'):
        """
        逆指値の買注文を行う
        """
        self.submit_user_and_pass()
        res = self.br.open(self.pages['buy']+str(code)+self.pages['inv'])
        set_encode(self.br, self.ENC)
        self.br.select_form(nr=0)
        self._set_order_propaty(quantity, price, limit, date, order, comp)
        self.br["trigger_price"] = str(trigger_price)
        self.br["hitokutei_trade_kbn"] = [CATEGORY[category]]
        self.br["password"] = self.password
        return self._confirm()

    def sell_order(self, code, quantity=None, price=None, 
                   limit=0, order='LIM_UNC', comp='MORE'):
        """
        売注文を行う
        """
        self.submit_user_and_pass()
        res = self.br.open(self.pages['sell']+str(code))
        set_encode(self.br, self.ENC)
        self.br.select_form(nr=0)
        self._set_order_propaty(quantity, price, limit, date, order, comp)
        self.br["password"] = self.password
        return self._confirm()

    def inv_sell_order(self, code, quantity=None, trigger_price=None, price=None, 
                       limit=0, order='LIM_UNC', comp='MORE'):
        """
        逆指値の売注文を行う
        """
        self.submit_user_and_pass()
        res = self.br.open(self.pages['sell']+str(code)+self.pages['inv'])
        set_encode(self.br, self.ENC)
        self.br.select_form(nr=0)
        self._set_order_propaty(quantity, price, limit, date, order, comp)
        self.br["trigger_price"] = str(trigger_price)
        self.br["password"] = self.password
        return self._confirm()

    def get_order_num_list(self):
        """
        オーダーのリストを取得する
        """
        self.submit_user_and_pass()
        res = self.br.open(self.pages['list'])
        soup = BeautifulSoup(res.read().decode(self.ENC))
        lists = soup.findAll("td", width="20%", align="center")
        mlist = [re.search("\d{6}", l.findAll("a")[0]['href']) for l in lists]
        return [m.group(0) for m in mlist]

    def get_order_info(self, order_num):
        """
        オーダーの情報を取得する
        """
        self.submit_user_and_pass()
        res = self.br.open(self.pages['correct'] + order_num)
        try:
            soup = BeautifulSoup(res.read().decode(self.ENC))
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
        self.submit_user_and_pass()
        res = self.br.open(self.pages['schedule'])
        soup = BeautifulSoup(res.read().decode(self.ENC))
        lists = soup.findAll("tr", bgcolor="#f9f9f9")
        r = re.compile(r'\d+')
        return int("".join(r.findall(lists[wday_step].find("td", align="right").contents[0])))

    def cancel_order(self, order_num):
        """
        注文のキャンセル
        """
        self.submit_user_and_pass()
        res = self.br.open(self.pages['cancel'] + order_num)
        set_encode(self.br, self.ENC)
        self.br.select_form(nr=0)
        self.br["password"] = self.password
        self.br.submit()

    def _set_order_propaty(self, quantity, price, limit, date, order, comp):
        """
        オーダー時の設定を行う
        """
        self.br["quantity"] = str(quantity)
        self.br["price"] = str(price)
        self.br["caLiKbn"] = [limit]
        if limit == 0:
            self.br["caLiKbn"] = ["today"]
        elif limit <= 6:
            self.br["caLiKbn"] = ["limit"]
            day = workdays.workday(datetime.date.today(), limit, holidays)
            self.br["limit"]=[str(day).replace("-","/")]
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
            time.sleep(2)
            res = self.br.open(req)
        except:
            raise "Cannot Order!"
        try:
            soup = BeautifulSoup(res.read().decode(self.ENC))
            inputs = soup.findAll("input")
            res.close()
            return inputs[0]["value"]
        except:
            raise "Cannot Get Order Code!"
