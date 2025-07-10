
"""
this file 
- imports and cleans eigenvalue data
- plots the modal map of the eigenvalues on the real-imaginary axis
- identifies critical eigenvalues through different clustering methods
- tests different parameters for the different clustering methods
- selects the best clustering method and parameters based on silhouette score
- identifies if there are cases without an eigenvalue in each cluster and 
  if so, moves closest eigenvalue to that cluster
- exports information on best clustering model to a csv file 

"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from sklearn.cluster import DBSCAN
from sklearn.cluster import OPTICS
from sklearn.neighbors import NearestNeighbors
from sklearn.neighbors import NearestCentroid
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.model_selection import RandomizedSearchCV
import matplotlib.cm as cm
from sklearn.preprocessing import StandardScaler
import copy
import joblib
import os


#%% Functions
def exclude_50Hz_eig(real_selected_df, imag_selected_df, plot_figure=True):
    
    imag_selected_df=imag_selected_df.round(3)

    imag_selected_no50Hz=pd.DataFrame()
    real_selected_no50Hz=pd.DataFrame()

    for i in real_selected_df.columns:
        imag_serie = imag_selected_df[imag_selected_df[i] != 314.159][i]  # Use boolean indexing instead of query
        real_serie = real_selected_df.loc[imag_serie.index,i]
        
        if i ==0:
            imag_selected_no50Hz=pd.DataFrame(imag_serie).copy(deep=True).reset_index(drop=True)
            real_selected_no50Hz=pd.DataFrame(real_serie).copy(deep=True).reset_index(drop=True)
        else:
            real_selected_no50Hz=real_selected_no50Hz.merge(pd.DataFrame(real_serie).reset_index(drop=True), how='outer', left_index=True, right_index=True)
            imag_selected_no50Hz=imag_selected_no50Hz.merge(pd.DataFrame(imag_serie).reset_index(drop=True), how='outer', left_index=True, right_index=True)

    if plot_figure:
        fig=plt.figure()
        ax=fig.add_subplot()
        ax.set_xlabel('Real Axis',fontsize=25)
        ax.set_ylabel('Imaginary Axis',fontsize=25)
        ax.set_xlim(x_region)
        ax.set_ylim(y_region)
        ax.tick_params(labelsize=20)
        fig.tight_layout()
        plt.grid()
        ax.scatter(real_selected_no50Hz,imag_selected_no50Hz, label='Eigenvalues')
        ax.legend(loc='lower center',bbox_to_anchor=(0.45, -0.65),fontsize=15, ncol=2)
        ax.set_title('Modal Map Zoom - No 50Hz eigs', fontsize=25)
        plt.show()
    return real_selected_no50Hz, imag_selected_no50Hz

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

def plot_clusters(X, labels, x_region, y_region, model, reassignment = 0, target_cluster_points = 0,target_point=0, centroid = 0 ):
    model_name = type(model).__name__.lower()
    unique_labels = np.unique(labels)
    fig = plt.figure()
    ax=fig.add_subplot()
    # label the clusters 
    scatter=ax.scatter(X[:, 0], X[:, 1], c=labels, cmap='viridis', marker='o')
    handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=scatter.cmap(scatter.norm(label)), markersize=10) for label in unique_labels]
    # ax.legend(handles=handles, labels=[str(label) for label in unique_labels], loc='lower left', bbox_to_anchor=(0, 0), fontsize=15, ncol=1)
    if reassignment == 0:
        if model_name == 'kmeans':
            centers = model.cluster_centers_
            ax.scatter(centers[:, 0], centers[:, 1], c='red', s=200, marker='x', label='Centers')  
            par_1_str = 'n_clusters=' + str(model.n_clusters)
            par_2_str = ''
            ax.text(-100, 210, par_1_str)
        elif model_name == 'optics':
            par_1_str = 'min_samples=' + str(model.min_samples)
            par_2_str = ''
            ax.text(-100, 210, par_1_str + '\nNumber of clusters: ' + str(len(unique_labels)))
        elif model_name == 'dbscan':
            par_1_str = 'eps=' + str(model.eps)
            par_2_str = ' min_samples=' + str(model.min_samples)
            ax.text(-100, 210, par_1_str  + par_2_str  + '\nNumber of clusters: ' + str(len(unique_labels)))
        else: print("wrong")
    if reassignment == 1:
        ax.scatter(target_cluster_points[:, 0], target_cluster_points[:, 1], color='yellow', s=100, label='Target Cluster')
        ax.scatter(target_point[0], target_point[1], color='red', edgecolor='black', s=150, label='Reassigned Point')
        ax.scatter(centroid[:, 0], centroid[:, 1], c='red', s=200, marker='x', label='Centroid')
    fig.subplots_adjust(top=0.5, bottom=0.2, left=0.2, right=0.9)
    ax.set_xlim(x_region)
    ax.set_ylim(y_region)
    ax.tick_params(labelsize=20)
    ax.set_xlabel('Real Axis',fontsize=25)
    ax.set_ylabel('Imaginary Axis',fontsize=25)
    ax.set_title(model_name.capitalize() + ' Clustering')
    ax.grid()
    fig.tight_layout(pad=4.0)
    
    if reassignment == 0:
        Images_folder = '../identification_of_critical_eigenvalues/Clustering_Training_Images'
        os.makedirs(Images_folder, exist_ok=True)  # Ensure folder exists
        save_path = os.path.join(Images_folder, model_name + '_' + par_1_str + '_' + par_2_str + '.png')
        plt.savefig(save_path)
        plt.close(fig)  
    else: 
        Images_folder = '../identification_of_critical_eigenvalues/DataSet_Clustering_Images'
        os.makedirs(Images_folder, exist_ok=True)  # Ensure folder exists
        save_path = os.path.join(Images_folder, 'point_reassignment.png')
        plt.savefig(save_path)
        plt.close(fig)  

def reassign_noise_points(X, labels):
    noise_points = X[labels == -1]
    if len(noise_points) > 0:
        clf = NearestCentroid()
        clf.fit(X[labels != -1], labels[labels != -1])  # Fit only non-noise points
        noise_labels = clf.predict(noise_points)
        labels[labels == -1] = noise_labels
    return labels


def import_and_clean(foldername):
    # import and clean the eigenvalue data
    df_real=pd.read_csv(f'{foldername}/case_df_real.csv')
    df_imag=pd.read_csv(f'{foldername}/case_df_imag.csv')

    # remove the empty rows (from the samples that didn't converge)
    df_real_clean = df_real.dropna(subset=['2'])
    df_imag_clean = df_imag.dropna(subset=['2'])

    # remove the first column and the  case_id column
    df_real_clean = df_real_clean.drop([df_real_clean.columns[0], 'case_id', 'Stability'], axis=1).reset_index(drop=True)
    df_imag_clean = df_imag_clean.drop([df_imag_clean.columns[0], 'case_id', 'Stability'], axis=1).reset_index(drop=True)
    df_clean = [df_real_clean, df_imag_clean]
    return df_clean
    
def get_clustering_region_data(x_region, y_region, df_real_clean, df_imag_clean):
    # gets the eigenvalues in the region 
    # also deletes the nan values and their cooresponding values from selected_real and selected_imag
    # also creates X (data for clustering algorithms)
    
    # select eigenvalues in the region
    selected_eig_real = df_real_clean[(df_real_clean > x_region[0]) & (df_real_clean < x_region[1])]
    selected_eig_imag = df_imag_clean[(df_imag_clean > y_region[0]) & (df_imag_clean < y_region[1])]
    
    # create two dataframes, one for real parts and one for imaginary parts.
    # Each dataframe will have dimensions n_eig x n_cases
    real_selected_df=pd.DataFrame()
    imag_selected_df=pd.DataFrame()
    
    for i in range(len(selected_eig_imag)): # for each row
        imag_selected=selected_eig_imag.loc[i,selected_eig_imag.columns].dropna() # removes nan values
        ind_imag_selected=imag_selected.index # indices of non-nan values 
        
        real_selected=selected_eig_real.iloc[i][ind_imag_selected].dropna() # out of the values in imag_selected, delete the nan values 
        imag_selected=imag_selected[real_selected.index]
        
        if i==0:
            real_selected_df=pd.DataFrame(real_selected).copy(deep=True).reset_index(drop=True)
            imag_selected_df=pd.DataFrame(imag_selected).copy(deep=True).reset_index(drop=True)
        else:
            real_selected_df=real_selected_df.merge(pd.DataFrame(real_selected).reset_index(drop=True), how='outer', left_index=True, right_index=True)
            imag_selected_df=imag_selected_df.merge(pd.DataFrame(imag_selected).reset_index(drop=True), how='outer', left_index=True, right_index=True)
    
    # drop all rows which contain any naan values 
    real_selected_df=real_selected_df.dropna()
    imag_selected_df=imag_selected_df.dropna()
    
    # Convert DataFrame to numpy arrays to flatten
    selected_eig_real_flat = real_selected_df.to_numpy().flatten()
    selected_eig_imag_flat = imag_selected_df.to_numpy().flatten()
    
    # Combine the cleaned real and imaginary parts
    X = np.vstack([selected_eig_real_flat, selected_eig_imag_flat]).T
    
    selected_df = [real_selected_df, imag_selected_df, X]
    return selected_df
   
if __name__ == "__main__":

    [df_real_clean, df_imag_clean]=import_and_clean('../results/datagen_ACOPF_LF09_seed17_nc5_ns5_d5_20241119_115327_8464')
    n_cases_clean= len(df_real_clean)
    
    # select the eigenvalues that have the highest real parts in each row 
    df_real_clean_max = df_real_clean[df_real_clean.columns[0:2]]
    df_imag_clean_max = df_imag_clean[df_imag_clean.columns[0:2]]
    
    #%% plot the full modal map with highest values 
    fig=plt.figure()
    ax=fig.add_subplot()
    ax.set_xlabel('Real Axis',fontsize=25)
    ax.set_ylabel('Imaginary Axis',fontsize=25)
    ax.tick_params(labelsize=20)
    fig.tight_layout(pad=5)
    plt.grid()
    ax.scatter(df_real_clean,df_imag_clean, label='Eigenvalues')
    ax.scatter(df_real_clean_max, df_imag_clean_max, label='Max Eigenvalues')
    ax.legend(loc='lower left', fontsize=15, ncol=1)  
    ax.set_title('Complete Modal Map', fontsize=25)
    plt.savefig("Complete Modal Map.png")  
    plt.close()  
    
    
        
    #%% plot the modal map for the region 
    
    x_region = [-115,20]
    y_region = [200,320]
    
    fig=plt.figure()
    ax=fig.add_subplot()
    ax.set_xlabel('Real Axis',fontsize=25)
    ax.set_ylabel('Imaginary Axis',fontsize=25)
    ax.set_xlim(x_region)
    ax.set_ylim(y_region)
    ax.tick_params(labelsize=20)
    fig.tight_layout(pad=4.0)
    plt.grid()
    ax.scatter(df_real_clean,df_imag_clean, label='Eigenvalues')
    ax.scatter(df_real_clean_max, df_imag_clean_max, label='Max Eigenvalues')
    ax.legend(loc='lower left', fontsize=15, ncol=1)  
    ax.set_title('Complete Clustering Region', fontsize=25)
    plt.savefig("Complete_Clustering_Region.png")  
    plt.close()  
    
    #%% get clustering region data
    [real_selected_df, imag_selected_df, X] = get_clustering_region_data(x_region, y_region, df_real_clean, df_imag_clean)
    
    
    #%% If you want to exclude 50 Hz eigenvalues
    
    # real_selected_no50Hz,imag_selected_no50Hz=exclude_50Hz_eig(real_selected_df, imag_selected_df)
    # real_selected_df=real_selected_no50Hz.copy(deep=True).dropna()
    # imag_selected_df=imag_selected_no50Hz.copy(deep=True).dropna()
    

    #%% K Means cluster
    cluster_method = 'KMeans'
    
    # test for different kvals (number of clusters)
    n_clusters = [2,3,4,5,6]
    K_Means_Results = pd.DataFrame({'cluster_method': [cluster_method] * len(n_clusters), 'n_clusters': n_clusters, 'parameter_2': [np.nan] * len(n_clusters), 'silhouette_score': [np.nan] * len(n_clusters)})
    counter = 0
    for i in n_clusters:
        kmeans = KMeans(n_init=10, n_clusters=i, random_state=42)
        kmeans.fit(X)  
        labels = kmeans.labels_  # Cluster labels for each data point
        K_Means_Results.loc[counter, 'silhouette_score'] = silhouette_score(X, labels)
        
        # unique_labels = np.unique(labels)
        # labels_reshape=labels.reshape(imag_selected_df.shape)
        # ClustersMissingEigs, SampleClusterPairs = check_cluster_memberships(labels_reshape, unique_labels)
        
        plot_clusters(X, labels, x_region, y_region, kmeans)
        counter += 1
    
    #%% Optics 
    cluster_method = 'Optics'
    
    # test for different min_samples 
    min_samples = [10, 100, 1000, 2000, 2200, 2300, 2400]
    Optics_results = pd.DataFrame({'cluster_method': [cluster_method] * len(min_samples), 'min_samples': min_samples,  'parameter_2': [np.nan] * len(min_samples), 'silhouette_score': [np.nan] * len(min_samples)})
    counter = 0
    for i in min_samples: 
        optics = OPTICS(min_samples=i)
        optics.fit(X)
        labels = optics.labels_
        labels = reassign_noise_points(X, labels)
        
        Optics_results.loc[counter, 'silhouette_score'] = silhouette_score(X, labels)
          
        # unique_labels = np.unique(labels)
        # labels_reshape=labels.reshape(imag_selected_df.shape)
        # ClustersMissingEigs, SampleClusterPairs = check_cluster_memberships(labels_reshape, unique_labels)
        
        plot_clusters(X, labels, x_region, y_region, optics)
        counter += 1
    
    #%% DBSCAN
    cluster_method = 'DBSCAN'
    
    # # k distance graph 
    # min_samples = 100  # Adjust this value to see the effect on the elbow
    # nbrs = NearestNeighbors(n_neighbors=min_samples).fit(X)
    # distances, indices = nbrs.kneighbors(X)
    # distances = np.sort(distances[:, -1])  # Distances to the `min_samples-th` nearest neighbor
    # plt.plot(distances)
    # plt.xlabel("Points sorted by distance")
    # plt.ylabel(f"{min_samples}-th Nearest Neighbor Distance")
    # plt.title("k-Distance Plot")
    # plt.show()
    
    dbscan = DBSCAN()
    eps =  [0.5, 1, 1.5, 2]  # chosen because they are elbow of kdistance graph 
    min_samples = [20, 40, 60, 80]
    param_grid = [(e, m) for e in eps for m in min_samples]
    DBSCAN_results = pd.DataFrame({
        'cluster_method': ['DBSCAN'] * len(param_grid),
        'eps': [p[0] for p in param_grid],
        'min_samples': [p[1] for p in param_grid],
        'silhouette_score': [np.nan] * len(param_grid)
    })
    counter = 0
    for i in eps:
        for j in min_samples:
            dbscan = DBSCAN(eps=i, min_samples=j)
            labels = dbscan.fit_predict(X)
            labels = reassign_noise_points(X, labels)
    
            DBSCAN_results.loc[counter, 'silhouette_score'] = silhouette_score(X, labels)
            
            # unique_labels = np.unique(labels)
            # labels_reshape=labels.reshape(imag_selected_df.shape)
            # ClustersMissingEigs, SampleClusterPairs = check_cluster_memberships(labels_reshape, unique_labels)
            
            plot_clusters(X, labels, x_region, y_region, dbscan)
            counter+=1
    
    #%% identify the best silhouette score from dataframe 
    
    # combine the dataframes 
    K_Means_Results = K_Means_Results.rename(columns={'n_clusters': 'parameter_1'})
    Optics_results = Optics_results.rename(columns={'min_samples': 'parameter_1'})
    DBSCAN_results = DBSCAN_results.rename(columns={'eps': 'parameter_1'})
    DBSCAN_results = DBSCAN_results.rename(columns={'min_samples': 'parameter_2'})
    Results = pd.concat([K_Means_Results, Optics_results, DBSCAN_results], axis=0, ignore_index=True)
    pd.DataFrame.to_csv(Results, 'clustering_selection_results.csv', index=False)
    
    
    # Get the row with the highest silhouette score
    highest_silhouette_row = Results.loc[Results['silhouette_score'].idxmax()]
    print("The best model is:\n",  highest_silhouette_row)
    
    
    # Run the best model again so that it can be saved 
    best_method = highest_silhouette_row.iloc[0]
    best_parameter1 = highest_silhouette_row.iloc[1]
    best_parameter2 = highest_silhouette_row.iloc[2] 
    
    if best_method == "KMeans":
        kmeans = KMeans(n_init=10, n_clusters=int(best_parameter1), random_state=42)
        kmeans.fit(X)
        labels = kmeans.labels_  
        best_model = kmeans
    elif best_method == "Optics":
        optics = OPTICS(min_samples=int(best_parameter1))
        optics.fit(X)
        labels = optics.labels_
        best_model = optics
    elif best_method == "DBSCAN":
        dbscan = DBSCAN(eps=best_parameter1, min_samples=int(best_parameter2))
        dbscan.fit(X)
        labels = dbscan.labels_
        best_model = dbscan
    
    # save the best model
    joblib.dump(best_model, 'best_model.joblib')
    

    
    
    