"""
This file plots the modal map of the eigenvalues on the real-imaginary axis
The critical eigenvalue group is identified by region selection (manually)
It calculates the damping index for the critical eigenvalues
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

#%% import and clean data
df_real=pd.read_csv('../results/datagen_ACOPF_LF09_seed17_nc5_ns5_d5_20241119_115327_8464/case_df_real.csv')
df_imag=pd.read_csv('../results/datagen_ACOPF_LF09_seed17_nc5_ns5_d5_20241119_115327_8464/case_df_imag.csv')

# remove the empty rows (from the samples that didn't converge)
df_real_clean = df_real.dropna(subset=['2'])
df_imag_clean = df_imag.dropna(subset=['2'])

# remove the first column and the  case_id column
df_real_clean = df_real_clean.drop([df_real_clean.columns[0], 'case_id', 'Stability'], axis=1)
df_imag_clean = df_imag_clean.drop([df_imag_clean.columns[0], 'case_id', 'Stability'], axis=1)

n_cases_clean= len(df_real_clean)

#%% Identify the critical eigenvalues manually
crit_eig_real = np.full(df_real_clean.shape, np.nan)
crit_eig_imag = np.full(df_imag_clean.shape, np.nan)
for ii in range(0,n_cases_clean): # for every row
    for jj in range(0,df_imag_clean.shape[1]): # for every column
        # if the point has a real value between -60 and 20  and an imaginary value between 200 and 305 or between -300 ad -200
        if (-60 < df_real_clean.iloc[ii, jj] < 20) and (
                (200 < df_imag_clean.iloc[ii, jj] < 305) or (-305 < df_imag_clean.iloc[ii, jj] < -200)
        ):
            # then add that to the crit_eig_real and crit_eig_imag
            crit_eig_real[ii,jj] = df_real_clean.iloc[ii, jj]
            crit_eig_imag[ii,jj] = df_imag_clean.iloc[ii, jj]

#%% plot the full modal map
fig=plt.figure()
ax=fig.add_subplot()
ax.scatter(df_real_clean,df_imag_clean, label='Eigenvalues')
ax.set_xlabel('Real Axis',fontsize=25)
ax.set_ylabel('Imaginary Axis',fontsize=25)
ax.set_title('Complete Modal Map', fontsize=25)
ax.tick_params(labelsize=20)
ax.legend(loc='lower center',bbox_to_anchor=(0.45, -0.65),fontsize=15, ncol=2)
fig.tight_layout()
plt.grid()
#plt.show()
#fig.savefig('1-Complete_Modal_Map.png')

# zoom in
fig = plt.figure(figsize=(10, 15))
ax=fig.add_subplot()
ax.scatter(df_real_clean,df_imag_clean, label='Eigenvalues')
ax.scatter(crit_eig_real,crit_eig_imag, label='Critical Eigenvalues')
ax.set_xlabel('Real Axis',fontsize=25)
ax.set_ylabel('Imaginary Axis',fontsize=25)
ax.tick_params(labelsize=20)
ax.set_xlim([-80,20])
ax.set_ylim([200,325])
ax.legend(loc='lower center',bbox_to_anchor=(0.45, -0.65),fontsize=15, ncol=2)
fig.tight_layout()
plt.grid()
#plt.show()
ax.set_title('Complete Manual Eigenvalue Selection', fontsize=25, pad=10)
#fig.savefig('Complete_Manual_Eigenvalue_Selection.png', bbox_inches='tight')


#%% Calculate the damping index

DI_crit_eig=1-(-crit_eig_real[:,0]/np.sqrt(crit_eig_real[:,0]**2+crit_eig_imag[:,0]**2))