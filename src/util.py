#!/bin/usr/env python
# -*- coding:utf-8 -*-

def lowpass_filter(tm, value, filt_value):
    """
    ローパスフィルター
    """
    if type(filt_value) == list:
        if len(filt_value) == 0:
            return value
        else:
            return [lowpass_filter(tm, value[i], filt_value[i]) for i in range(len(filt_value))]
    elif type(filt_value) == dict:
        if len(filt_value) == 0:
            return value
        else:
            return dict((key, lowpass_filter(tm, value[key], fval)) for key, fval in filt_value.items())
    elif type(filt_value) in (int, long, float):
        return (value + tm*filt_value)/(1.0+tm)
    else:
        return None

def calc_rate(obj, base):
    return (obj - base)/obj

