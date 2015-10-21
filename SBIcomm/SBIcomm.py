#!/bin/usr/env python
# -*- coding:utf-8 -*-
import re
import time
import datetime
import traceback
from dateutil.relativedelta import *
import mechanize
import urllib
import cookielib
from lxml import html

_NUM_PAT = re.compile(r'\d+\.*')
_DATE_PAT = re.compile(r'\d\d/\d\d \d\d:\d\d')

def _extract_num(string):
    if string == "-":
        return "None"
    else:
        return "".join(_NUM_PAT.findall(string))


def _extract_plus_minus_num(string):
    num = eval(_extract_num(string))
    if num is None:
        return None
    else:
        return eval(string[0] + "1.0") * float(num)


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

def _is_lim(order):
    if order == ORDER.MRK_UNC or \
            order == ORDER.MRK_YORI or \
            order == ORDER.MRK_HIKI or \
            order == ORDER.MRK_IOC:
        return False
    else:
        return True


class CATEGORY:
    SPC = '0'
    STD = '1'
    def __init__(self):
        pass


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

TODAY_MARKET, USA_MARKET, INDUSTRIES, \
EMERGING, ATTENTION, FORECAST, MARK = range(1, 8)

OPEN, CLOSE, MAX, MIN, VOLUME, GAIN_LOSS, RATE = range(7)

# 祝日の設定
def holidays_list(year):
    """
    yearの年の祝日のリストを返す

    :param year: 西暦
    :type year: int
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

def calc_workday(start_day, cnt):
    """
    start_dayからcnt日後の営業日を求める

    :type start_day: datetime
    :type cnt: int
    """
    holidays = holidays_list(start_day.year)
    rc = 0
    next_day = start_day
    while rc != cnt:
        next_day += datetime.timedelta(days=1)
        if not next_day in holidays and \
                next_day.weekday() <= 4:
            rc += 1
    return next_day


_BASE_URL = "https://k.sbisec.co.jp"
_STOCK_DIR = _BASE_URL + "/bsite/member/stock"
_ACC_DIR = _BASE_URL + "/bsite/member/acc"


class SBIcomm:
    """
    SBI証券のサイトをスクレイピングして株価の情報取得やオーダーの送信等のやりとりを行うクラス
    """
    # URL
    pages = {'top': _BASE_URL + "/bsite/visitor/top.do",
             'search': _BASE_URL + "/bsite/price/search.do",
             'market': _BASE_URL + "/bsite/market/indexDetail.do",
             'info': _BASE_URL + "/bsite/market/marketInfoDetail.do",
             'news': _BASE_URL + "/bsite/market/newsList.do",
             'foreign': _BASE_URL + "/bsite/market/foreignIndexDetail.do",
             'curr': _BASE_URL + "/bsite/market/forexDetail.do",
             'buy': _STOCK_DIR + "/buyOrderEntry.do",
             'sell': _STOCK_DIR + "/sellOrderEntry.do",
             'credit': _BASE_URL + "/bsite/price/marginDetail.do",
             'list': _STOCK_DIR + "/orderList.do",
             'correct': _STOCK_DIR + "/orderCorrectEntry.do",
             'cancel': _STOCK_DIR + "/orderCancelEntry.do",
             'schedule': _ACC_DIR + "/stockClearingScheduleList.do",
             'manege': _ACC_DIR + "/holdStockList.do"}

    ENC = "utf-8"
    def _x(self, path):
        return "//table/tr/td/table" + path

    def _add_url_param(self, url, params):
        return url + '?' + urllib.urlencode(params)
    
    def __init__(self, username, password,
                 proxy=None, proxy_user=None, proxy_password=None):
        """
        コンストラクタ

        :param str username: SBI証券でのユーザ名
        :param str password: パスワード
        :param str proxy: プロキシ
        :param str proxy_user: プロキシのユーザ名
        :param str proxy_password: プロキシのパスワード
        """
        self._username = username
        self._password = password
        self._proxy = proxy
        self._proxy_user = proxy_user
        self._proxy_password = proxy_password

    def _browser_open(self):
        """
        ブラウザの作成

        :return: ブラウザオブジェクト
        """
        br = mechanize.Browser()
        br.set_handle_robots(False)
        if not self._proxy is None:
            br.set_proxies(self._proxy)
            br.add_proxy_password(self._proxy_user, self._proxy_password)

        cj = cookielib.LWPCookieJar()
        br.set_cookiejar(cj)
        br.addheaders = [('User-agent', 'Chrome')]
        #br.set_debug_http(True)
        #br.set_debug_redirects(True)
        #br.set_debug_responses(True)
        return br

    def submit_user_and_pass(self):
        """
        トップページにユーザー名とパスワードを送信

        :return: ログインした後のブラウザオブジェクト
        """
        br = self._browser_open()
        br.open(self.pages['top'])
        br.select_form(name="form1")
        br["username"] = self._username
        br["password"] = self._password
        br.submit()
        return br

    def get_value(self, code):
        """
        現在の日付、株価を返す

        :param str code: 企業コード
        """
        br = self._browser_open()
        res = br.open(self.pages['search'])
        br.select_form(nr=0)
        br["ipm_product_code"] = str(code)
        res = br.submit()
        # 取得したhtmlを解析して日付と価格を求める
        doc = html.fromstring(res.read().decode(self.ENC))
        try:
            end_price = float(doc.xpath(self._x("/tr[2]/td/font/font"))[0].text.replace(",", ""))
            path_list = doc.xpath(self._x("/tr[@valign='top']/td[@nowrap][@align='right']/font"))
            start_price = float(_NUM_PAT.findall(path_list[1].text.replace(",",""))[0])
            max_price = float(_NUM_PAT.findall(path_list[2].text.replace(",",""))[0])
            min_price = float(_NUM_PAT.findall(path_list[4].text.replace(",",""))[0])
            path_list = doc.xpath(self._x("/tr[@valign='top']/td[@nowrap][@align='right']"))
            volume = int(_NUM_PAT.findall(path_list[2].text.replace(",",""))[0])
            # 日付の取得
            path_list = doc.xpath(self._x("/tr[2]/td[2]"))[0]
            num_list = _DATE_PAT.findall(path_list.text_content())
            date = datetime.datetime.strptime(num_list[0] + " " + str(datetime.date.today().year),
                                              '%m/%d %H:%M %Y')
            # 損益の取得
            num = doc.xpath(self._x("/tr[3]/td/font"))[0]
            if num is None:
                gain_loss = 0.0
            else:
                gain_loss = float(num.text)
            return date, (start_price, end_price, max_price, min_price, volume,
                          gain_loss, gain_loss / (end_price - gain_loss))
        except:
            print traceback.format_exc()
            print "Cannot Get Value! %s" % code
            return datetime.date.today(), None

    def get_market_index(self, index_name='nk225'):
        """
        市場の指標を返す

        :param str index_name: 市場の指標の種類
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
        br.select_form(nr=0)
        br["data_type"] = [index_name]
        req = br.click(type="submit", nr=0)
        res = br.open(req)
        doc = html.fromstring(res.read().decode(self.ENC))
        path_list = doc.xpath(self._x("/tr/td/form/table[@border='0']/tr/td[@nowrap]"))
        try:
            if kind == 'curr':
                end_price = float(_extract_num(path_list[1].xpath("font")[0].text.split('-')[0]))
                start_price = float(_extract_num(path_list[6].text))
                max_price = float(_extract_num(path_list[8].text))
                min_price = float(_extract_num(path_list[10].text))
            else:
                end_price = float(_extract_num(path_list[1].xpath("font")[0].text))
                start_price = float(_extract_num(path_list[5].text))
                max_price = float(_extract_num(path_list[7].text))
                min_price = float(_extract_num(path_list[9].text))
            try:
                if kind == 'curr':
                    gain_loss = _extract_plus_minus_num(path_list[4].xpath("font")[0].text)
                else:
                    gain_loss = _extract_plus_minus_num(path_list[3].xpath("font")[0].text)
            except IndexError:
                gain_loss = 0.0
            return (start_price, end_price, max_price, min_price,
                    gain_loss, gain_loss / (end_price - gain_loss))
        except:
            print traceback.format_exc()
            print "Cannot Get Value! %s" % index_name
            return (None, None, None, None, None, None)

    def get_nikkei_avg(self):
        """
        日経平均を取得する
        """
        return self.get_market_index()

    def get_market_info(self, info_no=TODAY_MARKET):
        """
        市場情報を取得する
        """
        doc = self._get_parser(self._add_url_param(self.pages['info'], {"id": TODAY_MARKET}))
        path_list = doc.xpath(self._x("/tr/td/table[@border='0']/tr[@valign='top']/td"))
        return "\n".join([path_list[1].text, path_list[3].text_content()])

    def get_market_news(self):
        """
        ニュースを取得する
        """
        br = self.submit_user_and_pass()
        urls = []
        for page in range(5):
            br.open(self._add_url_param(self.pages['news'], {"page": page}))
            for link in br.links(url_regex='newsDetail'):
                urls.append(BASE_URL + link.url)
        br.close()

        text_list = []
        for url in urls:
            br = self.submit_user_and_pass()
            res = br.open(url)
            doc = html.fromstring(res.read().decode(self.ENC))
            path_list = doc.xpath("//table/tr/td/table[@width='100%'][@cellspacing='0'][@cellpadding='0']/tr[not(@*)]/td[not(@*)]")
            text = path_list[0].text_content().replace("\n", "").replace("\t", "").replace("\r", "")
            text_list.append(text.rstrip(u"国内指標ランキング市況コメント海外指標外国為替"))
            br.close()
        return text_list

    def get_credit_record(self, code):
        """
        企業の信用情報を取得する
        """
        doc = self._get_parser(self._add_url_param(self.pages['credit'],
                                                   {"ipm_product_code": code, "market": "TKY"}))
        path_list = doc.xpath("//table/tr/td/table[@border='0'][@cellspacing='0'][@cellpadding='0']")
        records = {}
        try:
            l = path_list[4].xpath("tr/td[@align='right']")
            records["unsold"] = [eval(_extract_num(l[0].text)), _extract_plus_minus_num(l[1].text)]
            records["margin"] = [eval(_extract_num(l[2].text)), _extract_plus_minus_num(l[3].text)]
            if records["unsold"][0] is None or records["margin"][0] is None:
                records["ratio"] = None
            else:
                records["ratio"] = float(records["margin"][0])/float(records["unsold"][0])
        
            l = path_list[5].xpath("tr/td[@align='right']")
            records["lending_stock"] = {"new":eval(_extract_num(l[0].text)),
                                        "repayment":eval(_extract_num(l[1].text)),
                                        "balance":eval(_extract_num(l[2].text)),
                                        "ratio":_extract_plus_minus_num(l[3].text)}
            records["finance_loan"] = {"new":eval(_extract_num(l[4].text)),
                                       "repayment":eval(_extract_num(l[5].text)),
                                       "balance":eval(_extract_num(l[6].text)),
                                       "ratio":_extract_plus_minus_num(l[7].text)}
            if records["finance_loan"]["balance"] is None or records["lending_stock"]["balance"] is None:
                records["diff"] = None
            else:
                records["diff"] = records["finance_loan"]["balance"] - records["lending_stock"]["balance"]
            records["diff_ratio"] = _extract_plus_minus_num(l[9].text)
            records["balance_ratio"] = eval(_extract_num(l[10].text))
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
        br = self._init_open(self._add_url_param(self.pages['buy'],
                                                 {"ipm_product_code": code,
                                                  "market": "TKY",
                                                  "cayen.isStopOrder": str(inv).lower()}))
        br.select_form(nr=0)
        self._set_order_propaty(br, quantity, price, limit, order)
        if inv == True:
            br["trigger_zone"] = [comp]
            br["trigger_price"] = str(trigger_price)
        br["hitokutei_trade_kbn"] = [category]
        br["password"] = self._password
        return self._confirm(br)

    def sell_order(self, code, quantity=None, price=None,
                   limit=0, order=ORDER.LIM_UNC,
                   inv=False, comp=COMP.MORE, trigger_price=None):
        """
        売注文を行う
        """
        br = self._init_open(self._add_url_param(self.pages['sell'],
                                                 {"ipm_product_code": code,
                                                  "market": "TKY",
                                                  "cayen.isStopOrder": str(inv).lower()}))
        br.select_form(nr=0)
        self._set_order_propaty(br, quantity, price, limit, order)
        if inv == True:
            br["trigger_zone"] = [comp]
            br["trigger_price"] = str(trigger_price)
        br["password"] = self._password
        return self._confirm(br)

    def get_order_num_list(self):
        """
        オーダーのリストを取得する
        """
        doc = self._get_parser(self._add_url_param(self.pages['list'], {"cayen.comboOff": 1}))
        path_list = doc.xpath("//td[@width='20%'][@align='center']")
        mlist = [re.search("\d{6}", l.xpath("descendant::a")[0].attrib['href']) for l in path_list]
        return [m.group(0) for m in mlist]

    def get_order_info(self, order_num):
        """
        オーダーの情報を取得する
        """
        doc = self._get_parser(self._add_url_param(self.pages['correct'],
                                                   {"sec_id": "S", "page": 0, "torihiki_kbn": 1,
                                                    "REQUEST_TYPE": 3, "cayen.prevPage": "cayen.orderList",
                                                    "cayen.comboOff": 1, "order_no": order_num}))
        try:
            path_list = doc.xpath("//form[@action='/bsite/member/stock/orderCorrectEntry.do'][@method='POST']")
            code = _extract_num(path_list[0].xpath("descendant::td/b")[0].text)
            path_list = doc.xpath("//form[@action='/bsite/member/stock/orderCorrectConfirm.do'][@method='POST']")
            tds = path_list[0].xpath("descendant::td")
            return {'code': code, 'number': int(_extract_num(tds[3].text)), 'state': tds[1].text}
        except:
            raise ValueError, "Cannot get info %s!" % order_num

    def get_purchase_margin(self, wday_step=0):
        """
        指定した営業日後での買付余力を取得する
        """
        doc = self._get_parser(self.pages['schedule'])
        path_list = doc.xpath(self._x("/tr/td/table/tr/td[@align='right']"))
        return int(_extract_num(path_list[wday_step].text))

    def get_hold_stock_info(self):
        """
        現在の所持している株の情報を取得
        """
        doc = self._get_parser(self.pages['manege'])
        path_list = doc.xpath(self._x("/tr/td/table/tr/td/table/tr/td[@colspan or @align='right']"))
        stock_list = {}
        for l0, l1, l2, l3 in zip(path_list[0::5], path_list[1::5], path_list[2::5], path_list[4::5]):
            code = _extract_num(l0.text)
            stock_list[code] = {"value": int(_extract_num(l1.text)),
                                "number": int(_extract_num(l2.text)),
                                "gain": eval(l3.text_content()[0] + "1") * int(_extract_num(l3.text_content()))}
        return stock_list

    def get_total_eval(self):
        """
        現在の評価合計を取得する
        """
        doc = self._get_parser(self.pages['manege'])
        path_list = doc.xpath(self._x("/tr/td/table/tr/td/table/tr[@align='center']/td"))
        return int(_extract_num(path_list[1].text))

    def cancel_order(self, order_num):
        """
        注文のキャンセル
        """
        br = self._init_open(self._add_url_param(self.pages['cancel'],
                                                 {"sec_id": "S", "page": 0, "torihiki_kbn": 1,
                                                  "REQUEST_TYPE": 3, "cayen.prevPage": "cayen.orderList",
                                                  "cayen.comboOff": 1, "order_num": order_num}))
        br.select_form(nr=0)
        br["password"] = self._password
        br.submit()

    def _set_order_propaty(self, br, quantity, price, limit, order):
        """
        オーダー時の設定を行う
        """
        br["quantity"] = str(quantity)
        if _is_lim(order):
            br["price"] = str(price)
        if limit == 0:
            br["caLiKbn"] = ["today"]
        elif limit <= 6:
            br["caLiKbn"] = ["limit"]
            today = datetime.date.today()
            day = calc_workday(today, limit)
            br["limit"] = [day.strftime("%Y/%m/%d")]
        else:
            raise ValueError, "Cannot setting 6 later working day!"
        br["sasinari_kbn"] = [order]

    def _confirm(self, br):
        """
        確認画面での最終処理を行う
        """
        req = br.click(type="submit", nr=1)
        res = br.open(req)
        try:
            doc = html.fromstring(res.read().decode(self.ENC))
            path_list = doc.xpath(self._x("/tr/td/font"))
            error_msg = path_list[0].text
        except:
            pass
        br.select_form(nr=0)
        try:
            req = br.click(type="submit", nr=0)
            print "Submitting Order..."
        except:
            raise RuntimeError, "Cannot Order!"

        for _ in range(5):
            try:
                time.sleep(0.5)
                res = br.open(req)
                doc = html.fromstring(res.read().decode(self.ENC))
                path_list = doc.xpath("//input[@name='orderNum']")
                return path_list[0].attrib['value']
            except:
                error_msg = u"処理がタイムアウトしました。"
        raise ValueError, error_msg

    def _init_open(self, page):
        """
        ユーザのパスワードを送信してpageをオープンする
        """
        br = self.submit_user_and_pass()
        res = br.open(page)
        return br

    def _get_parser(self, page):
        """
        指定したページをパースするパーサを取得する
        """
        br = self.submit_user_and_pass()
        res = br.open(page)
        return html.fromstring(res.read().decode(self.ENC))


if __name__ == "__main__":
    import getpass
    username = raw_input("username: ")
    password = getpass.getpass("password: ")
    sbi = SBIcomm(username, password)
    print sbi.get_value("6758")
    sbi.buy_order("6752", 100, 614, inv=True, trigger_price=612)  # 買い注文
