"""
This file plots the modal map of the eigenvalues on the real-imaginary axis
It also identifies critical eigenvalues through different clustering methods
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from sklearn.cluster import SpectralClustering
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_samples, silhouette_score
import matplotlib.cm as cm

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

# complete is one when want all data, complete is 0 when using only the highest real eigenvalues in each row
complete = 1

#%% Filter the data to select only the highest real eigenvalue in each row

# #if complete == 0:
# # find the column of the maximum real eigenvalue for each row
# max_real_indices = df_real_clean.idxmax(axis=1)

# # create a mask that is the same dimensions as df_real_clean
# mask = pd.DataFrame(
#     False, index=df_real_clean.index, columns=df_real_clean.columns
# )
# for row_idx, col_idx in max_real_indices.items():
#     mask.at[row_idx, col_idx] = True

# apply the mask to keep only the corresponding real and imaginary values
df_real_clean_max = df_real_clean[df_real_clean.columns[0:2]]
df_imag_clean_max = df_imag_clean[df_imag_clean.columns[0:2]]

# # clustering region for the highest eigenvalue case
# x_region = [-1,20]
# y_region = [-400,400]
# #else:
# # clustering region for the complete case
# x_region = [-80,20]
# y_region = [200,325]

#%% create plots

# plot the full modal map
# fig=plt.figure()
# ax=fig.add_subplot()
# ax.scatter(df_real_clean,df_imag_clean, label='Eigenvalues')
# ax.set_xlabel('Real Axis',fontsize=25)
# ax.set_ylabel('Imaginary Axis',fontsize=25)
# ax.set_title('Complete Modal Map', fontsize=25)
# ax.tick_params(labelsize=20)
# ax.legend(loc='lower center',bbox_to_anchor=(0.45, -0.65),fontsize=15, ncol=2)
# fig.tight_layout()
# plt.grid()
# plt.show()
# #fig.savefig('1-Complete_Modal_Map.png')
#
# # zoom in
fig = plt.figure(figsize=(12, 15))
ax=fig.add_subplot()
ax.scatter(df_real_clean,df_imag_clean, label='Eigenvalues')
ax.scatter(df_real_clean_max,df_imag_clean_max, color='r', label='Most Right Eigenvalues')
# ax.scatter(crit_eig_real,crit_eig_imag, label='Critical Eigenvalues')
ax.set_xlabel('Real Axis',fontsize=25)
ax.set_ylabel('Imaginary Axis',fontsize=25)
ax.tick_params(labelsize=20)
# ax.set_xlim([-60,20])
# ax.set_ylim([200,330])
ax.legend(loc='lower center',bbox_to_anchor=(0.45, -0.65),fontsize=15, ncol=2)
fig.tight_layout()
plt.subplots_adjust(top=0.85)
plt.grid()
ax.set_title('Clustering Region', fontsize=25, pad=0)
plt.show()
# # # fig.savefig('Title.png', bbox_inches='tight')

x_region=[-60,20]
y_region=[200,330]

fig = plt.figure(figsize=(12, 15))
ax=fig.add_subplot()
ax.scatter(df_real_clean,df_imag_clean, label='Eigenvalues')
ax.scatter(df_real_clean_max,df_imag_clean_max, color='r', label='Most Right Eigenvalues')
# ax.scatter(crit_eig_real,crit_eig_imag, label='Critical Eigenvalues')
ax.set_xlabel('Real Axis',fontsize=25)
ax.set_ylabel('Imaginary Axis',fontsize=25)
ax.tick_params(labelsize=20)
ax.set_xlim(x_region)
ax.set_ylim(y_region)
ax.legend(loc='lower center',bbox_to_anchor=(0.45, -0.65),fontsize=15, ncol=2)
fig.tight_layout()
plt.subplots_adjust(top=0.85)
plt.grid()
ax.set_title('Clustering Region', fontsize=25, pad=0)
plt.show()
# # # fig.savefig('Title.png', bbox_inches='tight')



#%% clean the data before clustering

# select eigenvalues in the region
selected_eig_real = df_real_clean[(df_real_clean > x_region[0]) & (df_real_clean < x_region[1])]
selected_eig_imag = df_imag_clean[(df_imag_clean > y_region[0]) & (df_imag_clean < y_region[1])]

# Convert DataFrame to numpy arrays to flatten
selected_eig_real_flat = selected_eig_real.to_numpy().flatten()
selected_eig_imag_flat = selected_eig_imag.to_numpy().flatten()

# Remove NaN values using a valid mask
valid_mask = ~np.isnan(selected_eig_real_flat) & ~np.isnan(selected_eig_imag_flat)
selected_eig_real_clean = selected_eig_real_flat[valid_mask]
selected_eig_imag_clean = selected_eig_imag_flat[valid_mask]

# Combine the cleaned real and imaginary parts
X = np.vstack([selected_eig_real_clean, selected_eig_imag_clean]).T

#%% run clustering
#%% k means cluster
# k = 3  # Number of clusters
# kmeans = KMeans(n_init=10, n_clusters=k, random_state=42)
# kmeans.fit(X)
#
# labels = kmeans.labels_  # Cluster labels for each data point
# centers = kmeans.cluster_centers_  # Coordinates of the cluster centers
#
# fig = plt.figure()
# ax=fig.add_subplot()
# ax.scatter(X[:, 0], X[:, 1], c=labels, cmap='viridis', marker='o')
# ax.set_xlabel('Real Axis',fontsize=25)
# ax.set_ylabel('Imaginary Axis',fontsize=25)
# ax.tick_params(labelsize=20)
# ax.set_xlim(x_region)
# ax.set_ylim(y_region)
# ax.scatter(centers[:, 0], centers[:, 1], c='red', s=200, marker='x', label='Centers')  # Plot the centers
# ax.set_title('Complete K-Means Clustering')
# ax.set_xlabel('Real Axis')
# ax.set_ylabel('Imaginary Axis')
# ax.legend()
# ax.grid()
# fig.tight_layout()
# plt.show()
# fig.savefig('Complete_Kmeans_Clustering.png')

# # calculate the silhouette score
# range_n_clusters = [2, 3, 4, 5, 6]
#
# for n_clusters in range_n_clusters:
#     # Create a subplot with 1 row and 2 columns
#     fig, (ax1, ax2) = plt.subplots(1, 2)
#     fig.set_size_inches(18, 7)
#
#     # The 1st subplot is the silhouette plot
#     # The silhouette coefficient can range from -1, 1 but in this example all
#     # lie within [-0.1, 1]
#     ax1.set_xlim([-0.1, 1])
#     # The (n_clusters+1)*10 is for inserting blank space between silhouette
#     # plots of individual clusters, to demarcate them clearly.
#     ax1.set_ylim([0, len(X) + (n_clusters + 1) * 10])
#
#     # Initialize the clusterer with n_clusters value and a random generator
#     # seed of 10 for reproducibility.
#     clusterer = KMeans(n_init=10, n_clusters=n_clusters, random_state=42)
#     cluster_labels = clusterer.fit_predict(X)
#
#     # The silhouette_score gives the average value for all the samples.
#     # This gives a perspective into the density and separation of the formed
#     # clusters
#     silhouette_avg = silhouette_score(X, cluster_labels)
#     print(
#         "For n_clusters =",
#         n_clusters,
#         "The average silhouette_score is :",
#         silhouette_avg,
#     )
#
#     # Compute the silhouette scores for each sample
#     sample_silhouette_values = silhouette_samples(X, cluster_labels)
#
#     y_lower = 10
#     for i in range(n_clusters):
#         # Aggregate the silhouette scores for samples belonging to
#         # cluster i, and sort them
#         ith_cluster_silhouette_values = sample_silhouette_values[cluster_labels == i]
#
#         ith_cluster_silhouette_values.sort()
#
#         size_cluster_i = ith_cluster_silhouette_values.shape[0]
#         y_upper = y_lower + size_cluster_i
#
#         color = cm.nipy_spectral(float(i) / n_clusters)
#         ax1.fill_betweenx(
#             np.arange(y_lower, y_upper),
#             0,
#             ith_cluster_silhouette_values,
#             facecolor=color,
#             edgecolor=color,
#             alpha=0.7,
#         )
#
#         # Label the silhouette plots with their cluster numbers at the middle
#         ax1.text(-0.05, y_lower + 0.5 * size_cluster_i, str(i))
#
#         # Compute the new y_lower for next plot
#         y_lower = y_upper + 10  # 10 for the 0 samples
#
#     ax1.set_title("The silhouette plot for the various clusters.")
#     ax1.set_xlabel("The silhouette coefficient values")
#     ax1.set_ylabel("Cluster label")
#
#     # The vertical line for average silhouette score of all the values
#     ax1.axvline(x=silhouette_avg, color="red", linestyle="--")
#
#     ax1.set_yticks([])  # Clear the yaxis labels / ticks
#     ax1.set_xticks([-0.1, 0, 0.2, 0.4, 0.6, 0.8, 1])
#
#     # 2nd Plot showing the actual clusters formed
#     colors = cm.nipy_spectral(cluster_labels.astype(float) / n_clusters)
#     ax2.scatter(
#         X[:, 0], X[:, 1], marker=".", s=30, lw=0, alpha=0.7, c=colors, edgecolor="k"
#     )
#
#     # Labeling the clusters
#     centers = clusterer.cluster_centers_
#     # Draw white circles at cluster centers
#     ax2.scatter(
#         centers[:, 0],
#         centers[:, 1],
#         marker="o",
#         c="white",
#         alpha=1,
#         s=200,
#         edgecolor="k",
#     )
#
#     for i, c in enumerate(centers):
#         ax2.scatter(c[0], c[1], marker="$%d$" % i, alpha=1, s=50, edgecolor="k")
#
#     ax2.set_title("The visualization of the clustered data.")
#     ax2.set_xlabel("Feature space for the 1st feature")
#     ax2.set_ylabel("Feature space for the 2nd feature")
#
#     plt.suptitle(
#         "Silhouette analysis for KMeans clustering on sample data with n_clusters = %d"
#         % n_clusters,
#         fontsize=14,
#         fontweight="bold",
#     )
#
# plt.show()


#%% Create the SpectralClustering model
# n_clusters = 2  # Number of clusters you want to identify
# sc = SpectralClustering(n_clusters=n_clusters, affinity='nearest_neighbors', random_state=42)
# # Fit the model and predict the cluster labels
# labels = sc.fit_predict(X)
# # Visualize the clusters
# fig = plt.figure()
# ax=fig.add_subplot()
# ax.scatter(X[:, 0], X[:, 1], c=labels, cmap='viridis', marker='o')
# ax.set_xlabel('Real Axis',fontsize=25)
# ax.set_ylabel('Imaginary Axis',fontsize=25)
# ax.tick_params(labelsize=20)
# ax.set_xlim(x_region)
# ax.set_ylim(y_region)
# ax.set_title('Highest Values Spectral Clustering Results')
# ax.set_xlabel('Real Axis')
# ax.set_ylabel('Imaginary Axis')
# ax.legend()
# ax.grid()
# fig.tight_layout()
# plt.show()
# # fig.savefig('Highest_Values_Spectral_Clustering.png')
#
# # calculate silhouette score
# silhouette = silhouette_score(X, labels)
# print(f"Silhouette Score: {silhouette:.2f}")


#%% DBScan
dbscan = DBSCAN(eps=3, min_samples=10)
labels = dbscan.fit_predict(X)

# Plot the results
fig = plt.figure()
ax=fig.add_subplot()
ax.scatter(X[:, 0], X[:, 1], c=labels, cmap='viridis', marker='o')
ax.set_xlabel('Real Axis',fontsize=25)
ax.set_ylabel('Imaginary Axis',fontsize=25)
ax.tick_params(labelsize=20)
ax.set_xlim(x_region)
ax.set_ylim(y_region)
ax.set_title('DBSCAN Clustering With Highest Values')
ax.set_xlabel('Real Axis')
ax.set_ylabel('Imaginary Axis')
ax.legend()
ax.grid()
fig.tight_layout()
plt.show()
fig.savefig('Highest_Values_DBSCAN_Clustering.png')

# calculate silhouette score
# Exclude noise points
cluster_labels = labels[labels != -1]  # Exclude noise
filtered_X = X[labels != -1]           # Exclude noise points in data
silhouette = silhouette_score(filtered_X, cluster_labels)
print(f"Silhouette Score: {silhouette:.2f}")


#%% Calculate the damping index

#DI_crit_eig=1-(-crit_eig_real[:,0]/np.sqrt(crit_eig_real[:,0]**2+crit_eig_imag[:,0]**2))