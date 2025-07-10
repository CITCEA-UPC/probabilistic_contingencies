import pandas as pd
import os

def open_csv(path_results):
    csv_files = [file for file in os.listdir(path_results) if file.endswith('.csv')]
    results_dataframes=dict()
    for file in csv_files:
        results_dataframes[file.replace('.csv','')]=pd.read_csv(path_results+'/'+file,sep=',').drop(['Unnamed: 0'],axis=1)
    
    return results_dataframes, csv_files 

def perc_stability(df,dir_name):
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)
    print(dir_name)
    print('Feasible cases: '+str(len(df.query('Stable>=0'))/len(df)*100)+'%')
    print('Stable cases: '+str(len(df.query('Stable == 1'))/len(df)*100)+'% of total cases')
    print('Stable cases: '+str(len(df.query('Stable == 1'))/len(df.query('Stable>=0'))*100)+'% of feasible cases')
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)

