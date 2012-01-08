#!/bin/usr/env python
# -*- coding:utf-8 -*-

import csv

filename = "toushou1bu.csv"
csvfile = open(filename)

CODE = {}
for row in csv.reader(csvfile):
    CODE[row[1]] = row[0]
