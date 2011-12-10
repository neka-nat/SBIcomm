#!/bin/usr/env python
# -*- coding:utf-8 -*-
import sys, re
import time, datetime
import workdays
from dateutil.relativedelta import *
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

pat = re.compile(r'\d+')
def extract_num(string):
    return "".join(pat.findall(string))

COMP = {'MORE':'0', 'LESS':'1'}
ORDER = {'LIM_UNC':' ',   # 指値無条件
         'LIM_YORI':'Z',  # 指値寄指
         'LIM_HIKI':'I',  # 指値引指
         'LIM_HUSE':'F',  # 指値不成
         'LIM_IOC':'P',   # 指値IOC
         'MRK_UNC':'N',   # 成行無条件
         'MRK_YORI':'Y',  # 成行寄成
         'MRK_HIKI':'H',  # 成行引成
         'MRK_IOC':'O'}   # 成行IOC
CATEGORY = {'SPC':'0', 'STD':'1'}

# 祝日の設定
def holidays_list(year):
    equinox = [lambda y:int(20.8431 + 0.242194 * ( y - 1980)) - int((y - 1980)/4),
               lambda y:int(23.2488 + 0.242194 * ( y - 1980)) - int((y - 1980)/4)]
    holidays = [datetime.date(year, 1, 1),  # 元日
                datetime.date(year, 1, 1) + relativedelta(weekday=MO(+2)), # 成人の日
                datetime.date(year, 2, 11), # 建国記念日
                datetime.date(year, 3, equinox[0](year)), # 春分の日
                datetime.date(year, 4, 29), # 昭和の日
                datetime.date(year, 5, 3),  # 憲法記念日
                datetime.date(year, 5, 4),  # みどりの日
                datetime.date(year, 5, 5),  # こどもの日
                datetime.date(year, 7, 1) + relativedelta(weekday=MO(+3)), # 海の日
                datetime.date(year, 9, 1) + relativedelta(weekday=MO(+3)), # 敬老の日
                datetime.date(year, 9, equinox[1](year)), # 秋分の日
                datetime.date(year, 10, 1) + relativedelta(weekday=MO(+2)),# 体育の日
                datetime.date(year, 11, 3), # 文化の日
                datetime.date(year, 11, 23),# 勤労感謝の日
                datetime.date(year, 12, 23)]# 天皇誕生日
    # 振替休日の追加
    for holiday in holidays:
        if holiday.weekday() == 6:
            holidays.append(holiday+datetime.timedelta(days=1))
    return holidays

class SBIcomm:
    """
    SBI証券のサイトをスクレイピングして株価の情報取得やオーダーの送信等のやりとりを行うクラス
    """
    # URL
    DOMAIN = "https://k.sbisec.co.jp"
    STOCK_DIR = DOMAIN + "/bsite/member/stock"
    ACC_DIR = DOMAIN + "/bsite/member/acc"
    pages = {'top':DOMAIN + "/bsite/visitor/top.do",
             'search':DOMAIN + "/bsite/price/search.do",
             'market':DOMAIN + "/bsite/market/indexDetail.do",
             'buy':STOCK_DIR + "/buyOrderEntry.do?ipm_product_code=%d&market=TKY&cayen.isStopOrder=%s",
             'sell':STOCK_DIR + "/sellOrderEntry.do?ipm_product_code=%d&market=TKY&cayen.isStopOrder=%s",
             'list':STOCK_DIR + "/orderList.do?cayen.comboOff=1",
             'correct':STOCK_DIR + "/orderCorrectEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_no=%s",
             'cancel':STOCK_DIR + "/orderCancelEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_num=%s",
             'schedule':ACC_DIR + "/stockClearingScheduleList.do",
             'manege':ACC_DIR + "/holdStockList.do"}

    ENC = "cp932"
    SLEEP_TIME = 2

    logger = logging.getLogger("mechanize")
    logfile = open("sbicomm.log", 'w')
    logger.addHandler(logging.StreamHandler(logfile))
    logger.addHandler(logging.StreamHandler(sys.stdout))

    logger.setLevel(logging.INFO)

    def __init__(self, username=None, password=None,
                 proxy=None, proxy_user=None, proxy_password=None):
        self.username = username
        self.password = password
        self.proxy          = proxy
        self.proxy_user     = proxy_user
        self.proxy_password = proxy_password

    def _browser_open(self):
        br = mechanize.Browser()
        br.set_handle_robots(False)
        if not self.proxy is None:
            br.set_proxies(self.proxy)
            br.add_proxy_password(self.proxy_user, self.proxy_password)

        #br.set_debug_http(True)
        #br.set_debug_redirects(True)
        #br.set_debug_responses(True)
        return br

    def submit_user_and_pass(self):
        """
        トップページにユーザー名とパスワードを送信
        """
        br = self._browser_open()
        br.open(self.pages['top'])
        set_encode(br, self.ENC)
        br.select_form(name="form1")
        br["username"] = self.username
        br["password"] = self.password
        br.submit()
        #time.sleep(self.SLEEP_TIME)
        return br

    def get_value(self, code):
        """
        現在の日付、株価を返す
        """
        br = self._browser_open()
        res = br.open(self.pages['search'])
        set_encode(br, self.ENC)
        br.select_form(nr=0)
        br["ipm_product_code"] = str(code)
        res = br.submit()
        # 取得したhtmlを解析して日付と価格を求める
        html = res.read().decode(self.ENC)
        soup = BeautifulSoup(html)
        price_list = soup.findAll("tr", valign="top")
        try:
            cnt = 1 if price_list[2].find("font") is None else 0
            end_price = float(extract_num(price_list[2+cnt].find("font").contents[0]))
            num = price_list[3+cnt].find("font")
            m = [pat.findall(price_list[i+cnt].findAll("td", align="right")[0].contents[0].replace(",",""))[0] for i in range(4,7)]
            volume = int(extract_num(price_list[4+cnt].findAll("td", align="right")[1].contents[0]))
            num_list = pat.findall(price_list[2+cnt].findAll("td")[1].contents[1])
            if num is None:
                gain_loss = 0.0
            else:
                num_str = num.contents[0]
                gain_loss = eval(num_str[0]+"1.0")*float(extract_num(num_str))
            start_price = float(m[0])
            max_price = float(m[1])
            min_price = float(m[2])
            # 日付の取得
            date = datetime.date(datetime.date.today().year, int(num_list[0]), int(num_list[1]))
            return date, [start_price, end_price, max_price, min_price, volume, gain_loss, gain_loss/(end_price-gain_loss)]
        except:
            self.logger.info("Cannot Get Value! %d" % code)
            return datetime.date.today(), None

    def buy_order(self, code, quantity=None, price=None, limit=0, order='LIM_UNC',
                  category='SPC', inv=False, comp='MORE', trigger_price=None):
        """
        買注文を行う
        """
        br = self._init_open(self.pages['buy'] % (code, str(inv).lower()))
        br.select_form(nr=0)
        self._set_order_propaty(br, quantity, price, limit, order)
        if inv == True:
            br["trigger_zone"] = [COMP[comp]]
            br["trigger_price"] = str(trigger_price)
        br["hitokutei_trade_kbn"] = [CATEGORY[category]]
        br["password"] = self.password
        return self._confirm(br)

    def sell_order(self, code, quantity=None, price=None, limit=0, order='LIM_UNC',
                   inv=False, comp='MORE', trigger_price=None):
        """
        売注文を行う
        """
        br = self._init_open(self.pages['sell'] % (code, str(inv).lower()))
        br.select_form(nr=0)
        self._set_order_propaty(br, quantity, price, limit, order)
        if inv == True:
            br["trigger_zone"] = [COMP[comp]]
            br["trigger_price"] = str(trigger_price)
        br["password"] = self.password
        return self._confirm(br)

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
            code = int(extract_num(l.find("td").contents[0].contents[0]))
            l = soup.find("form", action="/bsite/member/stock/orderCorrectConfirm.do", method="POST")
            state = l.findAll("td")[1].contents[0]
            n_order = int(extract_num(l.findAll("td")[3].contents[0]))
            return {'code':code, 'number':n_order, 'state':state}
        except:
            raise "Cannot get info!", order_num

    def get_purchase_margin(self, wday_step=0):
        """
        指定した営業日後での買付余力を取得する
        """
        soup = self._get_soup(self.pages['schedule'])
        lists = soup.findAll("tr", bgcolor="#f9f9f9")
        return int(extract_num(lists[wday_step].find("td", align="right").contents[0]))

    def get_hold_stock_info(self):
        """
        現在の所持している株の情報を取得
        """
        soup = self._get_soup(self.pages['manege'])
        lists = soup.find("table", border="0", cellspacing="1", cellpadding="2", width="100%", bgcolor="#7E7ECC").findAll("tr")
        stock_list = []
        for l0, l1, l2 in zip(lists[0::3], lists[1::3], lists[2::3]):
            val_str = l2.contents[7].contents[0].contents[0]
            stock_list.append({"code":int(extract_num(l0.contents[0].contents[0])), 
                               "number":int(extract_num(l1.contents[7].contents[0])),
                               "val":int(extract_num(l1.contents[3].contents[0])),
                               "gain":eval(val_str[0]+"1")*int(extract_num(val_str))})
        return stock_list

    def get_total_eval(self):
        """
        現在の評価合計を取得する
        """
        soup = self._get_soup(self.pages['manege'])
        lists = soup.findAll("table", border="0", cellspacing="1", cellpadding="2", width="100%")
        try:
            return int(extract_num(lists[0].findAll("td")[1].contents[0]))
        except:
            raise "Cannot Get Total Evaluate!"

    def cancel_order(self, order_num):
        """
        注文のキャンセル
        """
        br = self._init_open(self.pages['cancel'] % order_num)
        br.select_form(nr=0)
        br["password"] = self.password
        br.submit()

    def _set_order_propaty(self, br, quantity, price, limit, order):
        """
        オーダー時の設定を行う
        """
        br["quantity"] = str(quantity)
        if order.startswith("LIM"):
            br["price"] = str(price)
        if limit == 0:
            br["caLiKbn"] = ["today"]
        elif limit <= 6:
            br["caLiKbn"] = ["limit"]
            today = datetime.date.today()
            day = workdays.workday(today, limit, holidays_list(today.year))
            br["limit"]=[day.strftime("%Y/%m/%d")]
        else:
            self.logger.info("Cannot setting 6 later working day!")
            raise "Cannot setting 6 later working day!"
        br["sasinari_kbn"] = [ORDER[order]]

    def _confirm(self, br):
        """
        確認画面での最終処理を行う
        """
        req = br.click(type="submit", nr=1)
        res = br.open(req)
        set_encode(br, self.ENC)
        br.select_form(nr=0)
        try:
            req = br.click(type="submit", nr=0)
            self.logger.info("Submitting Order...")
            time.sleep(self.SLEEP_TIME)
            res = br.open(req)
        except:
            self.logger.info("Cannot Order!")
            raise "Cannot Order!"
        try:
            html = res.read().decode(self.ENC)
            soup = BeautifulSoup(html)
            inputs = soup.findAll("input")
            res.close()
            return inputs[0]["value"]
        except:
            self.logger.info("Cannot Get Order Code!")
            raise "Cannot Get Order Code!"

    def _init_open(self, page):
        """
        ユーザのパスワードを送信してpageをオープンする
        """
        br = self.submit_user_and_pass()
        res = br.open(page)
        set_encode(br, self.ENC)
        return br

    def _get_soup(self, page):
        """
        指定したページをパースするパーサを取得する
        """
        br = self.submit_user_and_pass()
        res = br.open(page)
        html = res.read().decode(self.ENC)
        return BeautifulSoup(html)

if __name__ == "__main__":
    sbi = SBIcomm("hogehoge", "hogehoge")
    print sbi.buy_order(6758, 100, 1000, inv=True, trigger_price=999)
    print sbi.get_value(6758)
    print sbi.get_purchase_margin()
    print sbi.get_total_eval()
