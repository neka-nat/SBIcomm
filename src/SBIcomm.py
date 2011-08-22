#!/bin/usr/env python
# -*- coding:utf-8 -*-
import re, time, datetime
import mechanize
from BeautifulSoup import BeautifulSoup

import logging
import logging.config
logging.config.fileConfig('log.conf')

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

class SBIcomm:
    # URL
    DOMAIN = "https://k.sbisec.co.jp"
    STOCK_DIR = DOMAIN + "/bsite/member/stock"
    pages = {'top':DOMAIN + "/bsite/visitor/top.do",
             'search':DOMAIN + "/bsite/price/search.do",
             'buy':STOCK_DIR + "/buyOrderEntry.do?ipm_product_code=",
             'sell':STOCK_DIR + "/sellOrderEntry.do?ipm_product_code=",
             'list':STOCK_DIR + "/orderCancelEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1",
             'cancel':STOCK_DIR + "/orderCancelEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_num=",
             'inv':"&cayen.isStopOrder=true"}

    ENC = "cp932"

    logger = logging.getLogger("mechanize")

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
                  limit="today", date=None, order='LIM_UNC', comp='MORE', category='SPC'):
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
                      limit="today", date=None, order='LIM_UNC', comp='MORE', category='SPC'):
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
                   limit="today", date=None, order='LIM_UNC', comp='MORE'):
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
                       limit="today", date=None, order='LIM_UNC', comp='MORE'):
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
        if limit == "limit":
            self.br["limit"]=[date]
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
            print "Cannot Order"
            return None
        try:
            soup = BeautifulSoup(res.read().decode(self.ENC))
            inputs = soup.findAll("input")
            res.close()
            return inputs[0]["value"]
        except:
            print "Cannot Get Order Code"
            return None