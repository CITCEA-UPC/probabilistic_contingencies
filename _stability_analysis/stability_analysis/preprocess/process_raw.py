import re
import pandas as pd
from math import nan

HEADER_PATTERN = '^0 / END OF .+ DATA, BEGIN (.+) DATA$'


def header_found(line):
    result = re.match(HEADER_PATTERN, line)
    if result is not None:
        return result[1]

def next_dataset(f):
    line = f.readline()
    while not (data_name := header_found(line)):
        line = f.readline()
        if line == '':
            break
    return data_name

def process_header(line):
    line = line[2:]
    points = line.split(',')
    points = [point.strip() for point in points]
    return points

def process_data(line):
    points = line.split(',')
    points = [point.strip() for point in points]
    return points

def process_transformer_header(header,input_file):
    header2 = process_header(input_file.readline())
    header3 = process_header(input_file.readline())
    header4 = process_header(input_file.readline())
    header5 = process_header(input_file.readline())
    len1 = len(header)
    len2 = len(header2)
    len3 = len(header3)
    len4 = len(header4)
    len5 = len(header5)
    header.extend(header2)
    header.extend(header3)
    header.extend(header4)
    header.extend(header5)
    return header, len1, len2, len3, len4, len5

def process_transformer_line(header,input_file,len1, len2, len3, len4, len5):
    header.extend([nan] * (len1-len(header)))
    header2 = process_data(input_file.readline())
    header2.extend([nan] * (len2-len(header2)))
    header3 = process_data(input_file.readline())
    header3.extend([nan] * (len3-len(header3)))
    header4 = process_data(input_file.readline())
    header4.extend([nan] * (len4-len(header4)))
    header5 = [nan] * len5 #no line 5
    header.extend(header2)
    header.extend(header3)
    header.extend(header4)
    header.extend(header5)
    return header

def read_raw(raw_file):
           
    with open(raw_file, 'r') as input_file:
        first_line = input_file.readline()
        
        # T_global data
        second_line = input_file.readline()
        values = second_line.split(',')
        SBASE = float(values[1].strip())
        BASFRQ = float(values[5].split('/')[0].strip())  
        data_global = {'AREA': [],'SyncArea': [], 'BASKV': [], 'Sb_MVA': [SBASE], 'f_Hz': [BASFRQ], 'ref_bus': [], 'ref_element': []}
         
        notEOF = True    
        data_name = next_dataset(input_file)
        while(notEOF):        
            header = input_file.readline()
            header = process_header(header)
    
            match data_name:
                
                case "BUS":
                    results_bus = {'I': [], 'BASKV': [], 'IDE': [], 'AREA': [], 'VM': [], 'VA':[]}
                    while line := input_file.readline():
                        if data_name := header_found(line):
                            break
                        else:
                            data_line = process_data(line)
                            results_bus['I'].append(int(data_line[header.index('I')]))
                            results_bus['BASKV'].append(float(data_line[header.index('BASKV')]))
                            results_bus['IDE'].append(int(data_line[header.index('IDE')]))
                            results_bus['AREA'].append(int(data_line[header.index('AREA')]))
                            results_bus['VM'].append(float(data_line[header.index('VM')]))
                            results_bus['VA'].append(float(data_line[header.index('VA')]))  
                    results_bus = pd.DataFrame(results_bus)
                    
                case "BRANCH":
                    branch = {'I': [], 'J': [], 'R': [], 'X': [], 'B': [], 'STAT':[]}
                    while line := input_file.readline():
                        if data_name := header_found(line):
                            break
                        else:
                            data_line = process_data(line)
                            branch['I'].append(int(data_line[header.index('I')]))
                            branch['J'].append(int(data_line[header.index('J')]))
                            branch['R'].append(float(data_line[header.index('R')]))
                            branch['X'].append(float(data_line[header.index('X')]))
                            branch['B'].append(float(data_line[header.index('B')]))
                            branch['STAT'].append(int(data_line[header.index('STAT')]))       
                    branch = pd.DataFrame(branch)
                    
                case "LOAD":
                    load = {'I': [], 'AREA': [], 'PL': [], 'QL': [], 'IP': [], 'IQ': [], 'YP': [], 'YQ': [], 'STAT':[]}
                    while line := input_file.readline():
                        if data_name := header_found(line):
                            break
                        else:
                            data_line = process_data(line)
                            load['I'].append(int(data_line[header.index('I')]))
                            load['AREA'].append(int(data_line[header.index('AREA')]))
                            load['PL'].append(float(data_line[header.index('PL')]))
                            load['QL'].append(float(data_line[header.index('QL')]))
                            load['IP'].append(float(data_line[header.index('IP')]))
                            load['IQ'].append(float(data_line[header.index('IQ')]))
                            load['YP'].append(float(data_line[header.index('YP')]))
                            load['YQ'].append(float(data_line[header.index('YQ')]))
                            load['STAT'].append(int(data_line[header.index('STAT')]))  
                    load = pd.DataFrame(load)
                    
                case "GENERATOR":
                    generator = {'I': [], 'AREA': [], 'PG': [], 'QG': [], 'MBASE': [], 'STAT':[]}
                    while line := input_file.readline():
                        if data_name := header_found(line):
                            break
                        else:
                            data_line = process_data(line)
                            bus = int(data_line[header.index('I')])
                            generator['I'].append(bus)
                            generator['AREA'].append(results_bus.loc[results_bus['I'] == bus,'AREA'].values[0])
                            generator['PG'].append(float(data_line[header.index('PG')]))
                            generator['QG'].append(float(data_line[header.index('QG')]))
                            generator['MBASE'].append(float(data_line[header.index('MBASE')]))
                            generator['STAT'].append(int(data_line[header.index('STAT')]))  
                    generator = pd.DataFrame(generator)
                    
                case "TRANSFORMER":
                    header, len1, len2, len3, len4, len5 = process_transformer_header(header,input_file)
                    trafo = {'I': [], 'J': [], 'CZ': [], 'R12':[], 'X12':[], 'SBASE12': [], 'STAT':[]}
                    while line := input_file.readline():
                        if data_name := header_found(line):
                            break
                        else:
                            data_line = process_data(line)
                            data_line = process_transformer_line(data_line,input_file, len1, len2, len3, len4, len5)
                            trafo['I'].append(int(data_line[header.index('I')]))
                            trafo['J'].append(int(data_line[header.index('J')]))
                            trafo['CZ'].append(int(data_line[header.index('CZ')]))
                            trafo['R12'].append(float(data_line[header.index('R1-2')]))
                            trafo['X12'].append(float(data_line[header.index('X1-2')]))
                            trafo['SBASE12'].append(float(data_line[header.index('SBASE1-2')]))
                            trafo['STAT'].append(int(data_line[header.index('STAT')]))  
                    trafo = pd.DataFrame(trafo)
                
                #TODO: check with a raw file with multiple synchronous areas to adjust the parse process   
                case "AREA":
                    while line := input_file.readline():
                        if data_name := header_found(line):
                            break
                        else:
                            data_line = process_data(line)
                            data_global['AREA'].append(int(data_line[header.index('I')]))
                            data_global['SyncArea'].append(int(data_line[header.index('I')]))
                            slack_bus = int(data_line[header.index('ISW')]);
                            data_global['ref_bus'].append(slack_bus)
                            data_global['BASKV'].append(results_bus.loc[results_bus['I'] == slack_bus,'BASKV'].values[0])
                            data_global['ref_element'].append('UNDEFINED')
                    data_global['f_Hz'] = [data_global['f_Hz'][0]] * len(data_global['AREA'])
                    data_global['Sb_MVA'] = [data_global['Sb_MVA'][0]] * len(data_global['AREA'])
                    data_global = pd.DataFrame(data_global)
                    
                case _ :
                    while line := input_file.readline():
                        if data_name := header_found(line):
                            break
                        else:
                            pass
                     
            if not data_name:
                notEOF = False
    
    results_bus['SyncArea']=1
    branch['SyncArea']=1
    load['SyncArea']=1
    generator['SyncArea']=1
    trafo['SyncArea']=1
    #print('STATUS: .raw data has been read')
        
    raw_data = {
    'data_global': data_global,
    'results_bus': results_bus,
    'branch': branch,
    'load': load,
    'generator': generator,
    'trafo': trafo,
    }
         
    return raw_data