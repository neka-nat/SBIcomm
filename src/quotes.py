#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib

def realtime_quotes():
    gaitame_url = "http://www.gaitameonline.com/rateaj/getrate"
    url_data = urllib.urlopen(gaitame_url).read().strip("\r\n")
    data = eval(url_data)['quotes']
    res = {}
    for d in data:
        res[d['currencyPairCode']] = {'ask':float(d['ask']),
                                      'bid':float(d['bid']),
                                      'high':float(d['high']),
                                      'low':float(d['low']),
                                      'open':float(d['open'])}
    return res

if __name__ == "__main__":
    print realtime_quotes()
