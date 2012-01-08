#!/usr/bin/python
# -*- coding: utf-8 -*-

import re, datetime, urllib
from BeautifulSoup import BeautifulSoup

N_DATA = 5
OPEN, CLOSE, MAX, MIN, VOLUME = range(N_DATA)
UNSOLD, MARGIN, DIFF_UNSOLD, DIFF_MARGIN, RATIO = range(N_DATA)

pat = re.compile(r'\d+\.*')
def extract_num(string):
    return "".join(pat.findall(string))

def _extractStr(content):
  """extract strings from soup data which contains bold style"""
  found = content.findAll('b')
  if found :
    # <td><small><b>25,810</b></small></td>
    temp = content.b.string
  else:
    # <td><small>26,150</small></td>
    temp = content.small.string
  string = re.sub(",","",temp)
  return string

def _splitToTick(soup, kind=0):
  """ split a soup to a tick datum """
  # convert date format yyyy年m月d日 into yyyy/m/d
  date_str = soup.contents[1].small.string
  date_str = re.sub(u"日", u"", re.sub(u"[年月]", "/", date_str))
  date_temp = date_str.split("/")
  date = datetime.date(int(date_temp[0]),int(date_temp[1]),int(date_temp[2]))

  # extract other price values
  open_v   = float(_extractStr(soup.contents[3]))
  max_v    = float(_extractStr(soup.contents[5]))
  min_v    = float(_extractStr(soup.contents[7]))
  close_v  = float(_extractStr(soup.contents[9]))
  try:
    volume_v = float(_extractStr(soup.contents[11]))
  except:
    volume_v = None

  if kind == 0:
    return [date, open_v, close_v, max_v, min_v, volume_v]
  else:
    return [date, open_v, max_v, min_v, close_v, volume_v]
  
def getTick(code,end_date=None,start_date=None,length=500,kind=0):
  print "getting data of tikker %s from yahoo finance...   " % code

  # initialize
  scale = 8.0/5.0 # for skipping hollidays
  if end_date is None:
    # set default end_date = today
    end_date = datetime.date.today()
  if start_date is None:
    # set default end_date = today - length * scale
    start_date = end_date - datetime.timedelta(days=length*scale)
  else:
    length = (end_date - start_date).days
  print "get data from %s to %s" %(start_date, end_date)
  start_m, start_d, start_y = start_date.month, start_date.day, start_date.year
  end_m, end_d, end_y = end_date.month, end_date.day, end_date.year
  enc = 'euc-jp'

  # the tables of Yahoo finance JP contains up to 50 rows
  # thus parsing html must be done iteratively
  ts = [] # an array to store the result, [list_prices]
  niter = 0 # iteration counter
  while(niter < length) :
    # prepare BeautifulSoup object
    if kind == 0:
      url_t = "http://table.yahoo.co.jp/t?s=%s&a=%s&b=%s&c=%s&d=%s&e=%s&f=%s&g=d&q=t&y=%d&z=%s&x=.csv" \
          % (code, start_m, start_d, start_y, end_m, end_d, end_y,niter, code)
    else:
      url_t = "http://table.yahoo.co.jp/bt?s=%s.t&a=%s&b=%s&c=%s&d=%s&e=%s&f=%s&g=d&q=t&y=%d&z=%s&x=.csv" \
          % (code, start_m, start_d, start_y, end_m, end_d, end_y,niter, code)
    try:
      url_data = unicode(urllib.urlopen(url_t).read(), enc, 'ignore')
    except:
      break

    soup = BeautifulSoup(url_data)

    # the price data are stored in the following format
    """
    <tr align="right" bgcolor="#ffffff">
    <td><small>2007年10月4日</small></td>
    <td><small>64,300</small></td>
    <td><small>64,900</small></td>
    <td><small>63,900</small></td>
    <td><small><b>64,400</b></small></td>
    <td><small>1,058,900</small></td>
    <td><small>64,400</small></td>
    </tr><
    """
    # extract the list of price data from the table
    price_list = soup.findAll('tr',align="right",bgcolor="#ffffff")
    if len(price_list) == 0:
      break

    # split price_list each day
    for data in price_list:
      prices = _splitToTick(data, kind)
      ts.append(prices)
    
    # increment iteration counter
    niter += 50 # 50ずつ値が表示される

  return ts

def getNikkeiStockAverage(end_date=None,start_date=None,length=500):
  """
  日経平均(998407)の取得
  """
  return getTick(998407,end_date,start_date,length)

def getDetailInfo(code):
  url = "http://stocks.finance.yahoo.co.jp/stocks/detail/?code=%d" % code
  try:
    url_data = urllib.urlopen(url).read()
  except:
    return None
  
  soup = BeautifulSoup(url_data)

  lists = soup.findAll("dd")
  info = {}

  try:
    info["PER"] = float(extract_num(lists[11].contents[0].contents[0]))
  except:
    info["PER"] = None
  try:
    info["PBR"] = float(extract_num(lists[12].contents[0].contents[0]))
  except:
    info["PBR"] = None
  try:
    info["EPS"] = float(extract_num(lists[13].contents[0].contents[0]))
  except:
    info["EPS"] = None
  try:
    info["BPS"] = float(extract_num(lists[14].contents[0].contents[0]))
  except:
    info["BPS"] = None

  return info


if __name__ == "__main__":
  from pylab import *
  from matplotlib.dates import  DateFormatter, WeekdayLocator, DayLocator, MONDAY, num2date
  from matplotlib.finance import candlestick, plot_day_summary, candlestick2
  from matplotlib.dates import date2num

  print getDetailInfo(1515)
  stock_data = getTick(1515, length=50)
  credit_rec = getTick(1515, length=50, kind=1)
  stock_data.reverse()
  credit_rec.reverse()
  for i in range(len(stock_data)):
    stock_data[i][0] = date2num(stock_data[i][0])

  for i in range(len(credit_rec)):
    credit_rec[i][0] = date2num(credit_rec[i][0])

  mondays       = WeekdayLocator(MONDAY)  # major ticks on the mondays
  alldays       = DayLocator()            # minor ticks on the days
  weekFormatter = DateFormatter('%b %d')  # Eg, Jan 12
  dayFormatter  = DateFormatter('%d')     # Eg, 12

  fig = figure()
  fig.subplots_adjust(bottom=0.2)
  ax = fig.add_subplot(211)
  ax2 = fig.add_subplot(212)
  ax.xaxis.set_major_locator(mondays)
  ax.xaxis.set_minor_locator(alldays)
  ax.xaxis.set_major_formatter(weekFormatter)
  ax2.xaxis.set_major_formatter(weekFormatter)

  candlestick(ax, stock_data, width=0.6)
  credit_rec = map(list, zip(*credit_rec))
  ax2.plot(credit_rec[0], credit_rec[RATIO+1])

  ax.xaxis_date()
  ax2.xaxis_date()
  ax.autoscale_view()
  setp( gca().get_xticklabels(), rotation=45, horizontalalignment='right')

  show()
