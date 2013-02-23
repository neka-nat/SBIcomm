#!/bin/usr/env python
# -*- coding:utf-8 -*-
import sys
import re
import time
import datetime
import traceback
import workdays
from dateutil.relativedelta import *
import mechanize
from BeautifulSoup import *

def set_encode(br, enc):
    """
    サイトのエンコードを変更する
    これをしないとSBI証券ではWindows-31Jを用いているためうまくdecodeできない
    """
    br._factory.encoding = enc
    br._factory._forms_factory.encoding = enc
    br._factory._links_factory._encoding = enc


def getNavigableStrings(soup):
    if isinstance(soup, NavigableString):
        if type(soup) not in (Comment, Declaration) and soup.strip():
            yield soup
    elif soup.name not in ('script', 'style'):
        for c in soup.contents:
            for g in getNavigableStrings(c):
                yield g

pat = re.compile(r'\d+\.*')


def extract_num(string):
    return "".join(pat.findall(string))


def extract_plus_minus_num(string):
    return eval(string[0] + "1.0") * float(extract_num(string))


class COMP:
    MORE = '0'
    LESS = '1'
    def __init__(self):
        pass


class ORDER:
    LIM_UNC = ' '   # 指値無条件
    LIM_YORI = 'Z'  # 指値寄指
    LIM_HIKI = 'I'  # 指値引指
    LIM_HUSE = 'F'  # 指値不成
    LIM_IOC = 'P'   # 指値IOC
    MRK_UNC = 'N'   # 成行無条件
    MRK_YORI = 'Y'  # 成行寄成
    MRK_HIKI = 'H'  # 成行引成
    MRK_IOC = 'O'   # 成行IOC
    def __init__(self):
        pass


class CATEGORY:
    SPC = '0'
    STD = '1'
    def __init__(self):
        pass

TODAY_MARKET, USA_MARKET, INDUSTRIES, \
EMERGING, ATTENTION, FORECAST, MARK = range(1, 8)

OPEN, CLOSE, MAX, MIN, VOLUME, GAIN_LOSS, RATE = range(7)


class JP_IDX:
    nk225 = 'nk225'
    nk225f = 'nk225f'
    topix = 'topix'
    jasdaq_average = 'jasdaq_average'
    jasdaq_index = 'jasdaq_index'
    jasdaq_standard = 'jasdaq_standard'
    jasdaq_growth = 'jasdaq_growth'
    jasdaq_top20 = 'jasdaq_top20'
    j_stock = 'j_stock'
    mothers_index = 'mothers_index'
    jgb_long_future = 'jgb_long_future'
    def __init__(self):
        pass


class FR_IDX:
    ny_dow = 'ny_dow'
    nasdaq = 'nasdaq'
    ftse100 = 'ftse100'
    dax300 = 'dax300'
    hk_hansen = 'hk_hansen'
    def __init__(self):
        pass


class CURR_IDX:
    usd = 'usd'
    eur = 'eur'
    gbp = 'gbp'
    aud = 'aud'
    nzd = 'nzd'
    cad = 'cad'
    zar = 'zar'
    chf = 'chf'
    cny = 'cny'
    hkd = 'hkd'
    krw = 'krw'
    sgd = 'sgd'
    mxn = 'mxn'
    def __init__(self):
        pass

MARKET_INDICES = []
MARKET_INDICES.extend(JP_IDX.__dict__.keys())
MARKET_INDICES.extend(FR_IDX.__dict__.keys())
MARKET_INDICES.extend(CURR_IDX.__dict__.keys())
while '__module__' in MARKET_INDICES:
    MARKET_INDICES.remove('__module__')
while '__doc__' in MARKET_INDICES:
    MARKET_INDICES.remove('__doc__')


def get_indices():
    """
    SBI証券から得られるマーケット指標の種類を返す
    """
    return MARKET_INDICES


# 祝日の設定
def holidays_list(year):
    """
    yearの年の祝日のリストを返す
    """
    equinox = [lambda y:int(20.8431 + 0.242194 * (y - 1980)) \
                   - int((y - 1980) / 4),
               lambda y:int(23.2488 + 0.242194 * (y - 1980)) \
                   - int((y - 1980) / 4)]
    holidays = [datetime.date(year, 1, 1),
                datetime.date(year, 1, 2),
                datetime.date(year, 1, 3),
                datetime.date(year, 1, 1) \
                    + relativedelta(weekday=MO(+ 2)),  # 成人の日
                datetime.date(year, 2, 11),  # 建国記念日
                datetime.date(year, 3, equinox[0](year)),  # 春分の日
                datetime.date(year, 4, 29),  # 昭和の日
                datetime.date(year, 5, 3),   # 憲法記念日
                datetime.date(year, 5, 4),   # みどりの日
                datetime.date(year, 5, 5),   # こどもの日
                datetime.date(year, 7, 1) \
                    + relativedelta(weekday=MO(+3)),  # 海の日
                datetime.date(year, 9, 1) \
                    + relativedelta(weekday=MO(+3)),  # 敬老の日
                datetime.date(year, 9, equinox[1](year)),  # 秋分の日
                datetime.date(year, 10, 1) \
                    + relativedelta(weekday=MO(+2)),  # 体育の日
                datetime.date(year, 11, 3),   # 文化の日
                datetime.date(year, 11, 23),  # 勤労感謝の日
                datetime.date(year, 12, 23),  # 天皇誕生日
                datetime.date(year, 12, 29),
                datetime.date(year, 12, 30),
                datetime.date(year, 12, 31),
                datetime.date(year + 1, 1, 1),
                datetime.date(year + 1, 1, 2),
                datetime.date(year + 1, 1, 3)]

    # 振替休日の追加
    for holiday in holidays:
        if holiday.weekday() == 6:
            holidays.append(holiday + datetime.timedelta(days=1))
    return holidays


class SBIcomm:
    """
    SBI証券のサイトをスクレイピングして株価の情報取得やオーダーの送信等のやりとりを行うクラス
    """
    # URL
    DOMAIN = "https://k.sbisec.co.jp"
    STOCK_DIR = DOMAIN + "/bsite/member/stock"
    ACC_DIR = DOMAIN + "/bsite/member/acc"
    pages = {'top': DOMAIN + "/bsite/visitor/top.do",
             'search': DOMAIN + "/bsite/price/search.do",
             'market': DOMAIN + "/bsite/market/indexDetail.do",
             'info': DOMAIN + "/bsite/market/marketInfoDetail.do?id=%02d",
             'news': DOMAIN + "/bsite/market/newsList.do?page=%d",
             'foreign': DOMAIN + "/bsite/market/foreignIndexDetail.do",
             'curr': DOMAIN + "/bsite/market/forexDetail.do",
             'buy': STOCK_DIR + \
                 "/buyOrderEntry.do?ipm_product_code=%s&market=TKY&cayen.isStopOrder=%s",
             'sell': STOCK_DIR + \
                 "/sellOrderEntry.do?ipm_product_code=%s&market=TKY&cayen.isStopOrder=%s",
             'credit': DOMAIN + \
                 "/bsite/price/marginDetail.do?ipm_product_code=%s&market=TKY",
             'list': STOCK_DIR + \
                 "/orderList.do?cayen.comboOff=1",
             'correct': STOCK_DIR + \
                 "/orderCorrectEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_no=%s",
             'cancel': STOCK_DIR + \
                 "/orderCancelEntry.do?sec_id=S&page=0&torihiki_kbn=1&REQUEST_TYPE=3&cayen.prevPage=cayen.orderList&cayen.comboOff=1&order_num=%s",
             'schedule':ACC_DIR + "/stockClearingScheduleList.do",
             'manege':ACC_DIR + "/holdStockList.do"}

    ENC = "cp932"

    def __init__(self, username=None, password=None,
                 proxy=None, proxy_user=None, proxy_password=None):
        self._username = username
        self._password = password
        self._proxy = proxy
        self._proxy_user = proxy_user
        self._proxy_password = proxy_password

    def _browser_open(self):
        br = mechanize.Browser()
        br.set_handle_robots(False)
        if not self._proxy is None:
            br.set_proxies(self._proxy)
            br.add_proxy_password(self._proxy_user, self._proxy_password)

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
        br["username"] = self._username
        br["password"] = self._password
        br.submit()
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
            num = price_list[2 + cnt].find("font")
            end_price = float(extract_num(num.contents[0]))
            num = price_list[3 + cnt].find("font")
            m = [pat.findall(price_list[i + cnt].findAll("td", align="right")[0].contents[0].replace(",",""))[0] \
                     for i in range(4,7)]
            volume = int(extract_num(price_list[4 + cnt].findAll("td", align="right")[1].contents[0]))
            num_list = pat.findall(price_list[2 + cnt].findAll("td")[1].contents[1])
            if num is None:
                gain_loss = 0.0
            else:
                num_str = num.contents[0]
                gain_loss = extract_plus_minus_num(num_str)
            start_price = float(m[0])
            max_price = float(m[1])
            min_price = float(m[2])
            # 日付の取得
            date = datetime.date(datetime.date.today().year, int(num_list[0]), int(num_list[1]))
            return date, [start_price, end_price, max_price, min_price, volume,
                          gain_loss, gain_loss / (end_price - gain_loss)]
        except:
            print traceback.format_exc()
            print "Cannot Get Value! %s" % code
            return datetime.date.today(), None

    def get_market_index(self, index_name='nk225'):
        """
        市場の指標を返す
        """
        # index_nameがどのページから見られるかを探す
        if index_name in JP_IDX.__dict__.keys():
            kind = 'market'
        elif index_name in FR_IDX.__dict__.keys():
            kind = 'foreign'
        else:
            kind = 'curr'

        if kind == 'market':
            br = self._browser_open()
        else:
            br = self.submit_user_and_pass()
        br.open(self.pages[kind])
        set_encode(br, self.ENC)
        br.select_form(nr=0)
        br["data_type"] = [index_name]
        req = br.click(type="submit", nr=0)
        res = br.open(req)
        html = res.read().decode(self.ENC)
        soup = BeautifulSoup(html)
        price_list = soup.findAll("table", border="0", cellspacing="2",
                                  cellpadding="0", style="margin-top:5px;")
        l = price_list[0].findAll("font")
        try:
            if kind == 'curr':
                end_price = float(extract_num(l[0].contents[0].split('-')[0]))
            else:
                end_price = float(extract_num(l[0].contents[0]))
            try:
                gain_loss = extract_plus_minus_num(l[1].contents[0])
            except IndexError:
                gain_loss = 0.0
            l = price_list[1].findAll("td")
            start_price = float(extract_num(l[1].contents[0]))
            max_price = float(extract_num(l[3].contents[0]))
            min_price = float(extract_num(l[5].contents[0]))
            return [start_price, end_price, max_price, min_price,
                    gain_loss, gain_loss / (end_price - gain_loss)]
        except:
            print traceback.format_exc()
            print "Cannot Get Value! %s" % index_name
            return [None, None, None, None, None, None]

    def get_nikkei_avg(self):
        return self.get_market_index()

    def get_market_info(self, info_no=TODAY_MARKET):
        """
        市場情報を取得する
        """
        soup = self._get_soup(self.pages['info'] % info_no)
        text_list = soup.findAll("table", border="0", cellspacing="0",
                                 cellpadding="0", width="100%",
                                 style="margin-top:10px;")
        return '\n'.join(getNavigableStrings(text_list[1]))

    def get_market_news(self):
        """
        ニュースを取得する
        """
        br = self.submit_user_and_pass()
        urls = []
        for page in range(5):
            br.open(self.pages['news'] % page)
            set_encode(br, self.ENC)
            for link in br.links(url_regex='newsDetail'):
                urls.append(self.DOMAIN + link.url)
        br.close()

        text_list = []
        for url in urls:
            br = self.submit_user_and_pass()
            res = br.open(url)
            html = res.read().decode(self.ENC)
            soup = BeautifulSoup(html)
            lists = soup.findAll("table", width="100%",
                                 cellspacing="0", cellpadding="0")
            date = '\n'.join(getNavigableStrings(lists[2].contents[1].find("td").contents[3]))
            raw_text = ''.join(BeautifulSoup(html).findAll(text=True,
                                                           width="100%",
                                                           cellspacing="0",
                                                           cellpadding="0")).replace('\n', '')
            findx = raw_text.find(u"ニュース本文") + len(u"ニュース本文")
            lindx = raw_text.rfind(u"国内指標ランキング市況コメント")
            text_list.append([date, raw_text[findx:lindx]])
            br.close()

        return text_list

    def get_credit_record(self, code):
        """
        企業の信用情報を取得する
        """
        soup = self._get_soup(self.pages['credit'] % code)
        lists = soup.findAll("table", border="0",
                             cellspacing="0", cellpadding="0")
        records = {}
        try:
            l = lists[5].findAll("td")
            records["unsold"] = [int(extract_num(l[1].contents[0])),
                                 extract_plus_minus_num(l[3].contents[0])]
            records["margin"] = [int(extract_num(l[5].contents[0])),
                                 extract_plus_minus_num(l[7].contents[0])]
            records["ratio"] = float(records["margin"][0]) / float(records["unsold"][0])

            l = lists[6].findAll("td")
            records["lending_stock"] = {"new": int(extract_num(l[2].contents[0])),
                                        "repayment": int(extract_num(l[4].contents[0])),
                                        "balance": int(extract_num(l[6].contents[0])),
                                        "ratio": extract_plus_minus_num(l[8].contents[0])}
            records["finance_loan"] = {"new": int(extract_num(l[11].contents[0])),
                                       "repayment": int(extract_num(l[13].contents[0])),
                                       "balance": int(extract_num(l[15].contents[0])),
                                       "ratio": extract_plus_minus_num(l[17].contents[0])}
            records["diff"] = records["finance_loan"]["balance"] - records["lending_stock"]["balance"]
            records["diff_ratio"] = extract_plus_minus_num(l[21].contents[0])
            records["balance_ratio"] = float(extract_num(l[24].contents[0]))
        except:
            print traceback.format_exc()
            print "Cannot Get Value! %s" % code
        return records

    def buy_order(self, code, quantity=None, price=None,
                  limit=0, order=ORDER.LIM_UNC,
                  category=CATEGORY.SPC, inv=False,
                  comp=COMP.MORE, trigger_price=None):
        """
        買注文を行う
        """
        br = self._init_open(self.pages['buy'] % (code, str(inv).lower()))
        br.select_form(nr=0)
        self._set_order_propaty(br, quantity, price, limit, order)
        if inv == True:
            br["trigger_zone"] = [comp]
            br["trigger_price"] = str(trigger_price)
        br["hitokutei_trade_kbn"] = [category]
        br["password"] = self.password
        return self._confirm(br)

    def sell_order(self, code, quantity=None, price=None,
                   limit=0, order=ORDER.LIM_UNC,
                   inv=False, comp=COMP.MORE, trigger_price=None):
        """
        売注文を行う
        """
        br = self._init_open(self.pages['sell'] % (code, str(inv).lower()))
        br.select_form(nr=0)
        self._set_order_propaty(br, quantity, price, limit, order)
        if inv == True:
            br["trigger_zone"] = [comp]
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
            l = soup.find("form",
                          action="/bsite/member/stock/orderCorrectEntry.do",
                          method="POST")
            code = int(extract_num(l.find("td").contents[0].contents[0]))
            l = soup.find("form",
                          action="/bsite/member/stock/orderCorrectConfirm.do",
                          method="POST")
            state = l.findAll("td")[1].contents[0]
            n_order = int(extract_num(l.findAll("td")[3].contents[0]))
            return {'code': code, 'number': n_order, 'state': state}
        except:
            raise ValueError, "Cannot get info %d!" % order_num

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
        lists = soup.find("table", border="0",
                          cellspacing="1", cellpadding="2",
                          width="100%", bgcolor="#7E7ECC").findAll("tr")
        stock_list = {}
        for l0, l1, l2 in zip(lists[0::3], lists[1::3], lists[2::3]):
            val_str = l2.contents[7].contents[0].contents[0]
            code = int(extract_num(l0.contents[0].contents[0]))
            stock_list[code] = {"number": int(extract_num(l1.contents[7].contents[0])),
                                "value": int(extract_num(l1.contents[3].contents[0])),
                                "gain": eval(val_str[0] + "1")*int(extract_num(val_str))}
        return stock_list

    def get_total_eval(self):
        """
        現在の評価合計を取得する
        """
        soup = self._get_soup(self.pages['manege'])
        lists = soup.findAll("table", border="0",
                             cellspacing="1", cellpadding="2",
                             width="100%")
        return int(extract_num(lists[0].findAll("td")[1].contents[0]))

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
            br["limit"] = [day.strftime("%Y/%m/%d")]
        else:
            raise ValueError, "Cannot setting 6 later working day!"
        br["sasinari_kbn"] = [order]

    def _confirm(self, br, SLEEP_TIME=2):
        """
        確認画面での最終処理を行う
        """
        req = br.click(type="submit", nr=1)
        res = br.open(req)
        set_encode(br, self.ENC)
        br.select_form(nr=0)
        try:
            req = br.click(type="submit", nr=0)
            print "Submitting Order..."
            time.sleep(SLEEP_TIME)
            res = br.open(req)
        except:
            raise RuntimeError, "Cannot Order!"
        try:
            html = res.read().decode(self.ENC)
            soup = BeautifulSoup(html)
            inputs = soup.findAll("input")
            res.close()
            return inputs[0]["value"]
        except:
            raise ValueError, "Cannot Get Order Code!"

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
    print sbi.get_total_eval()
    print sbi.get_market_index("j_stock")
    print sbi.get_market_info()
    #print sbi.buy_order("6758", 100, 1000, inv=True, trigger_price=999)
    #print sbi.get_value("6758")
    #print sbi.get_purchase_margin()
