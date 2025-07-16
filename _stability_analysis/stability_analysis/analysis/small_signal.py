import pandas as pd
import numpy as np
from scipy import linalg
import matplotlib.pyplot as plt

# Set LaTeX font for matplotlib
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['DejaVu Serif'],
    'font.size': 8
})


def FEIG(ss_sys, plot=False):
    """
    Calculate the eigenvalues of a state-space system and optionally generate a pole map.

    Parameters:
    - ss_sys: State-space system (scipy.signal.lti or control.StateSpace)
    - plot: Boolean, optional, default is True
        If True, a pole map will be generated and displayed using matplotlib.

    Returns:
    - T_EIG: Pandas DataFrame
        Table containing mode ID, real parts, imaginary parts, frequencies, and damping ratios of eigenvalues.
    """
    
    # Compute state-space system eigenvalues
    eig = linalg.eig(ss_sys.A, left=False, right=False)
    
    # Compute real, imaginary, damping and frequency
    real = np.real(eig)
    imag = np.imag(eig)
    damp = -real/np.absolute(eig)
    freq = np.absolute(imag)/(2*np.pi)
    
    # Generate table    
    T_EIG = pd.DataFrame({'real':real, 'imag':imag, 'freq':freq, 'damp':damp})
    T_EIG = T_EIG.sort_values(by='real', ascending = False)
    
    # Add mode ID
    mode = list(range(1,len(T_EIG)+1))
    T_EIG.insert(0,"mode",mode)
    
    # Create pole map

    if plot:
        plt.figure(figsize=(5, 4))
        plt.scatter(real, imag, marker='x', color='blue')
        plt.title('Pole Map')
        plt.xlabel('Real')
        plt.ylabel('Imaginary')
        plt.grid(True)
        plt.show()
    
    return T_EIG


def FMODAL(ss_sys, plot):
    """
    Participation Factors Analysis

    Parameters:
    - ss_sys (StateSpace): State-space representation of the system.
    - plot (bool): Flag indicating whether to generate and display the participation factor heatmap.

    Returns:
    - df_nPF_red (DataFrame): DataFrame containing normalized Participation Factors (nPF) for each mode and state.
    """
    
    # Obtain left and right eigenvectors
    eig, vl, vr = linalg.eig(ss_sys.A, left=True, right=True)
    # Calculate Participation factors
    PFs = vl*vr
    # Normalize by the maximum absolute value in each column
    max_abs_PFs = np.max(np.abs(PFs), axis=0)
    # Calculate normalized Participation factors
    nPF = np.abs(np.dot(PFs, np.diag(1. / max_abs_PFs)))
    
    # Create T_EIG 
    real = np.real(eig) 
    imag = np.imag(eig)
    damp = -real/np.absolute(eig)
    freq = np.absolute(imag)/(2*np.pi)
    T_EIG = pd.DataFrame({'real':real, 'imag':imag, 'freq':freq, 'damp':damp})
    T_EIG = T_EIG.sort_values(by='real', ascending = False)    
    mode = list(range(1,len(T_EIG)+1)) # Add mode ID
    T_EIG.insert(0,"mode",mode)      
    
    # Obtain the indices
    idx = T_EIG.index.tolist()
    
    # Reorder nPF
    nPF_mode = nPF[:, idx]
    locs = np.any(nPF_mode >= 0, axis=1) # show all PFs
    nPF_red = nPF_mode[locs, :]

    # Display PFs colormap
    if plot:                 
        fig, ax = plt.subplots() 
        aspect_ratio = 0.5 
        heatmap = ax.imshow(nPF_red, cmap="gray_r", aspect=aspect_ratio, vmin = 0, vmax = 1)
        ax.set_title("Participation Factors")    
        
        # Set X axis
        ax.set_xlabel("Eigenvalues")        
        # Set major x-ticks at integer positions
        plt.xticks(np.arange(len(T_EIG)), T_EIG.mode)        
        # Set minor locator at positions halfway between integers
        minor_locator = plt.FixedLocator(np.arange(0.5, len(T_EIG), 1))
        plt.gca().xaxis.set_minor_locator(minor_locator)        
        # Hide the minor ticks
        plt.tick_params(which='minor', size=0)          
        
        # Set Y axis
        ax.set_ylabel("States")
        allStates = ss_sys.state_labels
        ax.set_yticks(np.arange(len(allStates)))
        ax.set_yticklabels(allStates)
        plt.yticks(fontsize=8)
        
        #cbar = plt.colorbar(heatmap)
        #cbar.set_label("Participation Factor")    
        
        # Loop over data dimensions and create text annotations.
        for (i, j), z in np.ndenumerate(nPF_red):
            if z >= 0.7:
                ax.text(j, i, '{:0.1f}'.format(z), ha='center', va='center', color = 'w')
            else:
                ax.text(j, i, '{:0.1f}'.format(z), ha='center', va='center', color = 'k')
        
        fig.tight_layout()
        plt.show()

    
    # Return PFs in dataframe format
    data = {'states': ss_sys.state_labels}
    for ID, values in zip(range(1,len(T_EIG)+1), zip(*nPF_red)):
        data[f'{ID}'] = list(values)
        
    df_nPF_red = pd.DataFrame(data)        
    
    return df_nPF_red
    
    
def FMODAL_REDUCED(ss_sys, plot, modeID):
    """
    Reduced Participation Factors Analysis for Specified Modes

    Parameters:
    - ss_sys (StateSpace): State-space representation of the system.
    - plot (bool): Flag indicating whether to generate and display the reduced participation factor heatmap.
    - modeID (list): List of mode IDs for which to perform the analysis. If None, all modes are considered.

    Returns:
    - T_modal (DataFrame): DataFrame containing eigenvalue information for the specified modes.
    - df_nPF_red (DataFrame): DataFrame containing normalized Participation Factors (nPF) for the specified modes and states.
    """
    
    # Obtain left and right eigenvectors
    eig, vl, vr = linalg.eig(ss_sys.A, left=True, right=True)
    # Calculate Participation factors
    PFs = vl*vr
    # Normalize by the maximum absolute value in each column
    max_abs_PFs = np.max(np.abs(PFs), axis=0)
    # Calculate normalized Participation factors
    nPF = np.abs(np.dot(PFs, np.diag(1. / max_abs_PFs)))
    
    # Create T_EIG 
    real = np.real(eig) 
    imag = np.imag(eig)
    damp = -real/np.absolute(eig)
    freq = np.absolute(imag)/(2*np.pi)
    T_EIG = pd.DataFrame({'real':real, 'imag':imag, 'freq':freq, 'damp':damp})
    T_EIG = T_EIG.sort_values(by='real', ascending = False)    
    mode = list(range(1,len(T_EIG)+1)) # Add mode ID
    T_EIG.insert(0,"mode",mode) 
    
    # Obtain the indices for the specified modeID          
    idx = T_EIG.index[T_EIG['mode'].isin(modeID)].tolist()
    
    # Reorder nPF
    nPF_mode = nPF[:, idx]
    locs = np.any(nPF_mode >= 0.005, axis=1) # avoid showing PFs lower than 0.005
    nPF_red = nPF_mode[locs, :]

    # Display PFs colormap
    if plot:                 
        fig, ax = plt.subplots() 
        aspect_ratio = 0.5 
        heatmap = ax.imshow(nPF_red, cmap="gray_r", aspect=aspect_ratio, vmin = 0, vmax = 1)
        ax.set_title("Participation Factors")    
        
        # Set X axis
        ax.set_xlabel("Eigenvalues")        
        # Set major x-ticks at integer positions
        plt.xticks(np.arange(len(modeID)), modeID)        
        # Set minor locator at positions halfway between integers
        minor_locator = plt.FixedLocator(np.arange(0.5, len(modeID), 1))
        plt.gca().xaxis.set_minor_locator(minor_locator)        
        # Hide the minor ticks
        plt.tick_params(which='minor', size=0)          
        
        # Set Y axis
        ax.set_ylabel("States")
        allStates = ss_sys.state_labels
        selected_states = [state for state, loc in zip(allStates, locs) if loc]
        ax.set_yticks(np.arange(len(selected_states)))
        ax.set_yticklabels(selected_states)
        plt.yticks(fontsize=8)
        
        #cbar = plt.colorbar(heatmap)
        #cbar.set_label("Participation Factor")    
        
        # Loop over data dimensions and create text annotations.
        for (i, j), z in np.ndenumerate(nPF_red):
            if z >= 0.7:
                ax.text(j, i, '{:0.2f}'.format(z), ha='center', va='center', color = 'w')
            else:
                ax.text(j, i, '{:0.2f}'.format(z), ha='center', va='center', color = 'k')
        
        fig.tight_layout()
        plt.show()
    
    # Display T_EIG rows that match modeID    
    T_modal = T_EIG[T_EIG['mode'].isin(modeID)]
    print(T_modal)
            
    # Return PFs in dataframe format
    data = {'states': selected_states}
    for ID, values in zip(modeID, zip(*nPF_red)):
        data[f'{ID}'] = list(values)
        
    df_nPF_red = pd.DataFrame(data)          
    
    return T_modal, df_nPF_red
    
        
def FMODAL_REDUCED_tol(ss_sys, plot, modeID, tol):
    """
    Reduced Participation Factors Analysis for Specified Modes with Tolerance
    
    Parameters:
    - ss_sys (StateSpace): State-space representation of the system.
    - plot (bool): Flag indicating whether to generate and display the reduced participation factor heatmap.
    - modeID (list): List of mode IDs for which to perform the analysis. If None, all modes are considered.
    - tol (float): Tolerance value to filter out low participation factors. Default is 0.005.
    
    Returns:
    - T_modal (DataFrame): DataFrame containing eigenvalue information for the specified modes.
    - df_nPF_red (DataFrame): DataFrame containing normalized Participation Factors (nPF) for the specified modes and states.
    """
    
    # Obtain left and right eigenvectors
    eig, vl, vr = linalg.eig(ss_sys.A, left=True, right=True)
    # Calculate Participation factors
    PFs = vl*vr
    # Normalize by the maximum absolute value in each column
    max_abs_PFs = np.max(np.abs(PFs), axis=0)
    # Calculate normalized Participation factors
    nPF = np.abs(np.dot(PFs, np.diag(1. / max_abs_PFs)))
    
    # Create T_EIG 
    real = np.real(eig) 
    imag = np.imag(eig)
    damp = -real/np.absolute(eig)
    freq = np.absolute(imag)/(2*np.pi)
    T_EIG = pd.DataFrame({'real':real, 'imag':imag, 'freq':freq, 'damp':damp})
    T_EIG = T_EIG.sort_values(by='real', ascending = False)    
    mode = list(range(1,len(T_EIG)+1)) # Add mode ID
    T_EIG.insert(0,"mode",mode) 
    
    # Obtain the indices for the specified modeID          
    idx = T_EIG.index[T_EIG['mode'].isin(modeID)].tolist()
    
    # Reorder nPF
    nPF_mode = nPF[:, idx]
    locs = np.any(nPF_mode >= tol, axis=1) # avoid showing PFs lower than 0.005
    nPF_red = nPF_mode[locs, :]
    allStates = ss_sys.state_labels
    selected_states = [state for state, loc in zip(allStates, locs) if loc]

    # Display PFs colormap
    if plot:
        fig, ax = plt.subplots() 
        aspect_ratio = 0.5 
        heatmap = ax.imshow(nPF_red, cmap="gray_r", aspect=aspect_ratio, vmin = 0, vmax = 1)
        ax.set_title("Participation Factors")    
        
        # Set X axis
        ax.set_xlabel("Eigenvalues")        
        # Set major x-ticks at integer positions
        plt.xticks(np.arange(len(modeID)), modeID)        
        # Set minor locator at positions halfway between integers
        minor_locator = plt.FixedLocator(np.arange(0.5, len(modeID), 1))
        plt.gca().xaxis.set_minor_locator(minor_locator)        
        # Hide the minor ticks
        plt.tick_params(which='minor', size=0)          
        
        # Set Y axis
        ax.set_ylabel("States")
        ax.set_yticks(np.arange(len(selected_states)))
        ax.set_yticklabels(selected_states)
        plt.yticks(fontsize=8)
        
        #cbar = plt.colorbar(heatmap)
        #cbar.set_label("Participation Factor")    
        
        # Loop over data dimensions and create text annotations.
        for (i, j), z in np.ndenumerate(nPF_red):
            if z >= 0.7:
                ax.text(j, i, '{:0.2f}'.format(z), ha='center', va='center', color = 'w')
            else:
                ax.text(j, i, '{:0.2f}'.format(z), ha='center', va='center', color = 'k')
        
        fig.tight_layout()
        plt.show()
    
    # Display T_EIG rows that match modeID    
    T_modal = T_EIG[T_EIG['mode'].isin(modeID)]
    #print(T_modal)
            
    # Return PFs in dataframe format
    data = {'states': selected_states}
    for ID, values in zip(modeID, zip(*nPF_red)):
        data[f'{ID}'] = list(values)
        
    df_nPF_red = pd.DataFrame(data)   
    
    return T_modal, df_nPF_red
