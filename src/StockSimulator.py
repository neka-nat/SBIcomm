# -*- coding: utf-8 -*-
#!/usr/bin/env python

import pickle
from operator import itemgetter
import code

class StockSimulator:
    def __init__(self, data = None):
        self.t = 0
        if not data is None:
            self.stock_values = data

    def load(self, filedir="./", sum_file = True):
        if sum_file == True:
            f = open("stock_data.dat", 'r')
            print "Loading datum..."
            self.stock_values = pickle.load(f)
            print "Finish loading datum"
            f.close()
        else:
            stock_data = {}
            filename = filedir + 'stock_data_%d.dat'
            print "Loading datum..."
            for c in code.CODE.values():
                data_file = open(filename % c)
                tmp_data = pickle.load(data_file)
                stock_data[c] = dict((d[0], d[1:]) for d in tmp_data)
                data_file.close()
            print "Finish loading datum"

            max_length = max([len(data) for data in stock_data.values()])
            for data in stock_data.values():
                if len(data) == max_length:
                    days = sorted(data.keys())
                    break

            self.stock_values = [[day, {}] for day in days]
            for key, data in stock_data.items():
                for i, d in enumerate(days):
                    if d in stock_data[key]:
                        self.stock_values[i][1][key] = stock_data[key][d]

    def goNextDay(self):
        self.t += 1

    def get_value(self, code):
        if code in self.stock_values[self.t][1]:
            return self.stock_values[self.t][0], self.stock_values[self.t][1][code]
        else:
            return self.stock_values[self.t][0], None

    def getStockValue(self):
        return self.stock_values[self.t][1]

    def getNowDay(self):
        return self.stock_values[self.t][0]

    def getTomorrow(self):
        return self.stock_values[self.t+1][0]

    def getNextData(self):
        return self.stock_values[self.t+1][1]

    def getLastData(self):
        return self.stock_values[-1][1]

    def isLastDay(self):
        if self.t >= len(self.stock_values)-1:
            return True
        else:
            return False

    def saveFile(self):
        f = open("stock_data.dat", 'w')
        pickle.dump(self.stock_values, f)
        f.close()

