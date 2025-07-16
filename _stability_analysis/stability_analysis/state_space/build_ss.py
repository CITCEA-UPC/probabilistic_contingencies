import control as ct
from stability_analysis.state_space import interconnect
import pandas as pd

def save_ss_matrices_fun(ss,path,filename):
    pd.DataFrame.to_csv(pd.DataFrame(ss.A),path+filename+'_A.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.B),path+filename+'_B.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.C),path+filename+'_C.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.D),path+filename+'_D.csv',index=False,header=False)

def select_io(l_blocks,varin,varout):
    
    inputNames = []
    outputNames = []
    
    for ss_block in l_blocks:
        inputNames.extend(ss_block.input_labels)
        outputNames.extend(ss_block.output_labels)
    
    outputNames = sorted(list(set(outputNames)))    
    inputNames  = list(set(inputNames) - set(outputNames))
    inputNames = sorted(list(set(inputNames)))
    
    # Check if varin are external inputs
    valid_input = [var in inputNames for var in varin]
    if not all(valid_input):
        print("input is not valid")
        
    # Check if varout are external outputs
    if varout[0] == 'all':
        varout = outputNames
    else:
        valid_output = [var in outputNames for var in varout]
        if not all(valid_output):
            raise RuntimeError("output is not valid")  

    return varin, varout 


def connect(l_blocks, l_states, inputs, outputs, connect_fun='append_and_connect',save_ss_matrices=False):    
    
    if connect_fun=='interconnect':
        ss_sys = ct.interconnect(l_blocks, states = l_states, inputs = inputs, outputs = outputs, check_unused = False)    

        if save_ss_matrices == True:
            save_ss_matrices_fun(ss_sys,
                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                     f'{ss_sys=}'.split('=')[0])
    elif connect_fun == 'append_and_connect':
        ss_sys = interconnect.interconnect(l_blocks, states = l_states, inputs = inputs, outputs = outputs, check_unused = False)    

        
        if save_ss_matrices == True:
            save_ss_matrices_fun(ss_sys,
                                 'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                 f'{ss_sys=}'.split('=')[0])                                       
            
    #ss_sys._remove_useless_states() 
    return ss_sys




