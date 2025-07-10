# created to run PCA and visualize data

import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objs as go

# import data
file_path = r'../results/ACOPF_standalone_seed16_nc3_ns100_20241014_162634_9593/case_df_op.csv'
data = pd.read_csv(file_path)
print("The data has", data.shape[0], "rows and", data.shape[1], "columns")
# print(data.head()) # Display the first few rows of the DataFrame
# print(data.dtypes) # data types

# get rid of missing data
print("The data has", data.isna().sum().sum(), "missing data points") # see if there is data missing
filtered_data = data.dropna() #drops rows with missing data
print("The filtered data has", filtered_data.shape[0], "rows and", filtered_data.shape[1], "columns")

# Extract the 'Stable' column before scaling
stability = filtered_data['Stable'].values  # Store it as a NumPy array for further use

# Scale the data
scaler = StandardScaler()
scaled_data = scaler.fit_transform(filtered_data)

#PCA with percentage of variance preserved
pca = PCA(n_components=0.95) # to preserve 95% of the dimensionality
PCAPercent = pca.fit_transform(scaled_data)

# plot explained variance as a function of dimensions
pca_full = PCA()
pca_full.fit(scaled_data)
explained_variance = pca_full.explained_variance_ratio_
cumulative_variance = np.cumsum(explained_variance)

plt.figure(figsize=(10, 6))
plt.plot(range(1, len(cumulative_variance) + 1), cumulative_variance, marker='o', linestyle='--')
plt.title('Cumulative Explained Variance by Number of Dimensions')
plt.xlabel('Number of Dimensions')
plt.ylabel('Cumulative Explained Variance')
plt.xlim(1, len(cumulative_variance))
plt.ylim(0, 1)
plt.grid()
plt.axhline(y=0.95, color='r', linestyle='--', label='95% Variance Threshold')  # Optional threshold line
plt.legend()
plt.show()

# print variance information
# print("Explained Variance:", explained_variance)
# print("Cumulative Explained Variance:", cumulative_variance)
n_components = np.argmax(cumulative_variance >= 0.95) + 1  # Number of components to retain for 95% variance
print("Number of components to retain for 95%:", n_components)

# Creation of correlation matrix
corr = data.iloc[:,1:].corr(method='spearman')  # method{‘pearson’, ‘kendall’, ‘spearman’}

# plot a 2D plot with the first two principle components
pca2 = PCA(n_components=2)
top_2_principal_components = pca2.fit_transform(scaled_data)

# Define conditions for stability
conditions = [
    stability == 1,  # Green for 1
    stability == 0   # Red for 0
]

# Define corresponding colors
choices = ['green', 'red']

# Use np.select to assign colors
colors = np.select(conditions, choices, default='black')  # Black for others

# Create a DataFrame with the two principal components
pc_df2 = pd.DataFrame(data=top_2_principal_components, columns=['PC1', 'PC2'])

# Scatter plot of the first two principal components
plt.figure(figsize=(8, 6))
#plt.scatter(PCAPercent[:, 0], PCAPercent[:, 1], c=colors, alpha=0.7)
plt.scatter(top_2_principal_components[:, 0], top_2_principal_components[:, 1], c=colors, alpha=0.7)
plt.title('Scatter plot of the first two principal components')
plt.xlabel('Principal Component 1')
plt.ylabel('Principal Component 2')
plt.grid(True)
plt.show()

# plot a 3D plot with the first three principle components
pca3 = PCA(n_components=3)
top_3_principal_components = pca3.fit_transform(scaled_data)

fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111, projection='3d')

ax.scatter(top_3_principal_components[:, 0], top_3_principal_components[:, 1], top_3_principal_components[:, 2], c=colors, marker='o', alpha=0.7)

# Set labels
ax.set_xlabel('Principal Component 1')
ax.set_ylabel('Principal Component 2')
ax.set_zlabel('Principal Component 3')
ax.set_title('3D Scatter Plot of the First Three Principal Components')

plt.show()

# plot interactive 3D plot
scatter = go.Scatter3d(
    x=top_3_principal_components[:, 0],
    y=top_3_principal_components[:, 1],
    z=top_3_principal_components[:, 2],
    mode='markers',
    marker=dict(
        size=5,
        color=colors,
        opacity=0.8
    )
)

layout = go.Layout(
    scene=dict(
        xaxis_title='PC 1',
        yaxis_title='PC 2',
        zaxis_title='PC 3'
    ),
    title="3D Scatter plot of Top 3 Principle Components",
)

fig = go.Figure(data=[scatter], layout=layout)
fig.show()

