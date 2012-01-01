# -*- coding: utf-8 -*-
#!/usr/bin/env python

import pickle
import code

class StockSimulator:
    def __init__(self, data = None):
        self.t = 0
        self.w = 0
        if not data is None:
            self.stock_values = data

    def load(self, filedir="./"):
        f = open("stock_data.dat", 'r')
        print "Loading datum..."
        self.stock_values = pickle.load(f)
        print "Finish loading datum"
        f.close()

        f = open("credit_records.dat", 'r')
        print "Loading datum..."
        self.credit_records = pickle.load(f)
        print "Finish loading datum"
        f.close()

    def goNextDay(self):
        self.t += 1
        if self.stock_values[self.t][0] >= self.credit_records[self.w+1][0]:
            self.w += 1

    def get_value(self, code):
        if code in self.stock_values[self.t][1]:
            return self.stock_values[self.t][0], self.stock_values[self.t][1][code]
        else:
            return self.stock_values[self.t][0], None

    def getStockValue(self):
        return self.stock_values[self.t][1]

    def get_credit_record(self, code):
        if code in self.credit_records[self.w][1]:
            credit_records = self.credit_records[self.w][1][code]
            ret = {}
            ret["unsold"] = [credit_records[0], credit_records[2]]
            ret["margin"] = [credit_records[1], credit_records[3]]
            ret["ratio"] = credit_records[4]
            return ret
        else:
            return None

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
