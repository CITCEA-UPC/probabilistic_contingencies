"""
Calculates the damping index for the best clustering model  
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from sklearn.cluster import DBSCAN
from sklearn.cluster import OPTICS
from sklearn.cluster import HDBSCAN
import matplotlib.cm as cm
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import copy
import joblib
from clustering_selection import import_and_clean
from clustering_selection import get_clustering_region_data
from clustering_selection import plot_clusters
from joblib import dump, load
import json
import os

def check_cluster_memberships(labels_reshape, k):
    ClustersMissingEigs = 0
    SampleClusterPairs = []  # List to store (sample, cluster) pairs
    
    for i in range(labels_reshape.shape[1]):  # For every column (sample)
        for l in k:  # For each cluster
            if not any(labels_reshape[:, i] == l): 
                print(f'There is no eigenvalue from sample {i} in cluster {l}')
                ClustersMissingEigs = 1
                SampleClusterPairs.append((i, l))  # Append the (sample, cluster) pair
    
    return ClustersMissingEigs, SampleClusterPairs

def reassign_eigenvalues(real_selected_df, imag_selected_df, X, labels, x_region, y_region, model):
    model_name = type(model).__name__.lower()
    # if there are samples without an eigenvalue in each cluster, then reassign the closest eigenvalue in the sample to that cluster
    unique_labels = np.unique(labels)
    labels_reshape=labels.reshape(imag_selected_df.shape)
    ClustersMissingEigs, SampleClusterPairs = check_cluster_memberships(labels_reshape, unique_labels)
    
    # # if there are samples that do not have an eigenvalue in each cluster
    if ClustersMissingEigs == 1:
        for i in range(len(SampleClusterPairs)): # for each samplecluster pair 
            
            # calculate the centroid of the cluster 
            centroid = np.array([X[labels == SampleClusterPairs[i][1]].mean(axis=0)])
            
            # values in the sample:
            real = real_selected_df.T.iloc[SampleClusterPairs[i][0],:]
            imag = imag_selected_df.T.iloc[SampleClusterPairs[i][0],:]
            samplevals = pd.concat([real, imag], axis=1).reset_index(drop=True)
            
            min_distance = float('inf')  # Start with a very large number
            min_index = -1  # To store the index of the minimum distance
            
            # for each value in sample 
            for j in range(len(samplevals)):
                # Calculate the Euclidean distance between the center and the sample 
                distance = np.sqrt(np.sum((samplevals.iloc[j].values - centroid) ** 2))
                
                # Check if this distance is the minimum
                if distance < min_distance:
                    min_distance = distance
                    min_index = j
                    
            # plot the clustering region and highlight the target cluster and the target point 
            target_cluster_points = X[labels == SampleClusterPairs[i][1]]
            target_point = samplevals.iloc[min_index].values
            plot_clusters(X, labels, x_region, y_region, model, 1, target_cluster_points, target_point,  centroid)
            # this will save 1 figure for reassignment, not all of them
            
            # reassign the eigenvalue to that cluster 
            labels_reshape[min_index,SampleClusterPairs[i][0]] = SampleClusterPairs[i][1]
   
    return labels_reshape 
#%% import X, real_selected_df, imag_selected_df

# get the data to run the model on (testing data)
# loaded_data = "../results/datagen_ACOPF_LF09_seed17_nc5_ns5_d5_20241119_115327_8464" # training data 
#loaded_data = "../results/datagen_ACOPF_LF09_seed8_nc3_ns3_d5_20250123_000244_4541"
#loaded_data = "../results/ACOPF_standalone_NREL_LF095_seed16_nc3_ns100_20250203_154241_9253"
loaded_data = "../results/ACOPF_standalone_NREL_LF085_seed24_nc3_ns1000_20250219_172120_5243"
[df_real_clean, df_imag_clean]=import_and_clean(loaded_data)

# make a json file with the data_number in it so the number can be transported for regression selection scripts
data_number = loaded_data[-4:]
with open('data_number.json', 'w') as file:
    json.dump(data_number, file)

# same region as clustering section script 
x_region = [-115,20]
y_region = [200,320]
[real_selected_df, imag_selected_df, X] = get_clustering_region_data(x_region, y_region, df_real_clean, df_imag_clean)

# Load the model
model = load('best_model.joblib')
model_name = type(model).__name__.lower()

# Use the model
labels = model.predict(X)

# calculate the silhouette score for the tested data 
silhouette_score = silhouette_score(X, labels)

#plot the modal map 
fig = plt.figure()
ax=fig.add_subplot()
scatter=ax.scatter(X[:, 0], X[:, 1], c=labels, cmap='viridis', marker='o')
fig.subplots_adjust(top=0.5, bottom=0.2, left=0.2, right=0.9)
ax.set_xlim(x_region)
ax.set_ylim(y_region)
ax.tick_params(labelsize=20)
ax.set_xlabel('Real Axis',fontsize=25)
ax.set_ylabel('Imaginary Axis',fontsize=25)
ax.set_title('Clustering For Dataset ' + data_number)
ax.grid()
fig.tight_layout(pad=4.0)
Images_folder = '../identification_of_critical_eigenvalues/DataSet_Clustering_Images'
os.makedirs(Images_folder, exist_ok=True)  # Ensure folder exists
save_path = os.path.join(Images_folder, data_number + 'clustering.png')
plt.savefig(save_path)
plt.close(fig) 

#%% if there are samples without an eigenvalue in each cluster, then reassign the closest eigenvalue in the sample to that cluster
labels_reshape = reassign_eigenvalues(real_selected_df, imag_selected_df, X, labels, x_region, y_region, model)

#%% Calculate the damping ratios for each eigenvalue 
labels_reshape=labels.reshape(imag_selected_df.shape)
labels_reshape_T=labels_reshape.T
unique_labels = np.unique(labels)

# calculate the damping ratios of all the eigenvalues 
drs_all= np.full_like(labels_reshape_T, np.nan, dtype = float)
for row_idx, row in enumerate(labels_reshape_T):
    for col_idx, value in enumerate(row):
        drs_all[row_idx, col_idx] =  (-real_selected_df.T.iloc[row_idx, col_idx]/np.sqrt(real_selected_df.T.iloc[row_idx, col_idx]**2+imag_selected_df.T.iloc[row_idx, col_idx]**2))

# calcualte the damping ratios for the eigenvalues in each cluster 
drs_clustered = {}  
# go through each label 
for i in unique_labels:
    # initialize an empty DI array that is the same size as labels_reshape_T
    dr = np.full_like(labels_reshape_T, np.nan, dtype = float)
    for row_idx, row in enumerate(labels_reshape_T):
        for col_idx, value in enumerate(row):
            if value == i: # if the label is the label we are looking for
                dr[row_idx, col_idx] =  (-real_selected_df.T.iloc[row_idx, col_idx]/np.sqrt(real_selected_df.T.iloc[row_idx, col_idx]**2+imag_selected_df.T.iloc[row_idx, col_idx]**2))
    drs_clustered[i] = dr
       
# identify critical eigenvalues 
for l in unique_labels:
    X_cl=X[labels==l]
    if X_cl[:,0].max()>=0:
        #print('Cluster '+str(l)+' collects critical eigenvalues')
        crit_cluster=l

#%% calculate the damping indices for each operational point 

# calculate damping indices using all eigenvalues
DIs_all=np.zeros([drs_all.shape[0],1])
for i in range(drs_all.shape[0]):
    if np.all(np.isnan(drs_all[i, :])):
        DIs_all[i, 0] = np.nan  # Assign NaN if no valid values exist
    else:
        DIs_all[i,0]=1-min(drs_all[i,~np.isnan(drs_all[i,:])])

# calculate damping indices using only eigenvalues in the critical cluster 
drs_crit=drs_clustered[crit_cluster]
DIs_crit=np.zeros([drs_crit.shape[0],1])
for i in range(drs_crit.shape[0]):
    if np.all(np.isnan(drs_crit[i, :])):
        DIs_crit[i, 0] = np.nan  # Assign NaN if no valid values exist
    else:
        DIs_crit[i,0]=1-min(drs_crit[i,~np.isnan(drs_crit[i,:])])
       
    
#%% create the csv with the inputs and add a column with the DIs  

case_op=pd.read_csv(f'{loaded_data}/case_df_op.csv')
# remove the rows with na in column V1 (the cases that didn't converge)
case_op = case_op.dropna(subset=['V1'])

case_op_crit = case_op.copy()
case_op_crit['DI_crit'] = DIs_crit
pd.DataFrame.to_csv(case_op_crit, f'DI_crit_{loaded_data[-4:]}.csv', index=False)

case_op_all = case_op.copy()
case_op_all['DI_all']= DIs_all
pd.DataFrame.to_csv(case_op_all, f'DI_all_{loaded_data[-4:]}.csv', index=False)



