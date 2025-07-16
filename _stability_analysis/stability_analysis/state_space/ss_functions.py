import pandas as pd
import numpy as np
import control as ct
from control.matlab import ss

# %% FILTERS

def SS_LOW_PASS(k, tau, input, output, state):
    
    A = np.array([[-1 / tau]])    
    B = np.array([[1]])            
    C = np.array([[k / tau]])           
    D = np.array([[0]])   
    
    ss_lp = ss(A, B, C, D, inputs = input, outputs = output, states = state)    
    return ss_lp

def tf_LOW_PASS(k,Ts):
    return ct.tf([k],[Ts, 1])    

def tf_WASH_OUT(Tw):
    return ct.tf([Tw, 0],[Tw, 1])    
    
def tf_LEAD_LAG(Tnum,Tden):
    return ct.tf([Tnum, 1],[Tden, 1])    

# %% ARITHMETICS

def SS_GAIN(k, input, output):

    A = np.empty(0)
    B = np.empty(0)
    C = np.empty(0)
    D = np.array([[k]])
    
    ss_gain = ss(A, B, C, D, inputs = input, outputs = output)     
    return ss_gain


def SS_ERROR(input_ref, input_sub, output):

    A = np.empty(0)
    B = np.empty((0, 2))
    C = np.empty((0, 2))
    D = np.array([[1, -1]])
    
    ss_error = ss(A, B, C, D, inputs = [input_ref, input_sub], outputs = output)     
    return ss_error

def SS_PROD(NAMEQ,VALQ0,NAMED,VALD0,NAMEOUT):

    A = np.empty(0)
    B = np.empty((0, 2))
    C = np.empty((0, 2))
    D = np.array([[VALD0, VALQ0]])
    
    ss_prod = ss(A, B, C, D, inputs = [NAMEQ, NAMED], outputs = NAMEOUT)     
    return ss_prod

def SS_ADD(input_ref, input_sub, output):

    A = np.empty(0)
    B = np.empty((0, 2))
    C = np.empty((0, 2))
    D = np.array([[1, 1]])
    
    ss_add = ss(A, B, C, D, inputs = [input_ref, input_sub], outputs = output)     
    return ss_add


# %% ROTATION

def SS_ROTATE(etheta_0, var_q0, var_d0, direction, u, y):
    
    if direction == "g2l":
        k = -1
    elif direction == "l2g":
        k = 1

    A = np.empty(0)
    B = np.empty((0, 3))
    C = np.empty((0, 2))
    D = np.array([[np.cos(etheta_0), k * np.sin(etheta_0), -np.sin(etheta_0) * var_q0 + k * np.cos(etheta_0) * var_d0],
                  [-k * np.sin(etheta_0), np.cos(etheta_0), -k * np.cos(etheta_0) * var_q0 - np.sin(etheta_0) * var_d0]])
    
    ss_rot = ss(A, B, C, D, inputs = u, outputs = y) 
    return ss_rot
