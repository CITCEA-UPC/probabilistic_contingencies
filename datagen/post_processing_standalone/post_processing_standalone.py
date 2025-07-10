import os
from utils_pp_standalone import *

ncig_list=['10','11','12']
path='../results/'

dir_names=[dir_name for dir_name in os.listdir(path) if dir_name.startswith('ACOPF_standalone_NREL_LF')]
for dir_name in dir_names:
    path_results = os.path.join(path, dir_name)
    
    results_dataframes, csv_files= open_csv(path_results)
    
    perc_stability(results_dataframes['case_df_op'],dir_name)


