"""
selects regression model using only using damping indices created from eigencalues in the critical cluster

"""
# from pyearth import Earth
# from pyearth import export
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import make_scorer, r2_score, mean_absolute_error
from sklearn.linear_model import LinearRegression, Lasso, Ridge, ElasticNet
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.neural_network import MLPRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.externals.joblib import Parallel, delayed
import os
import json


def compare_models(models_list, X, Y, Data_size, n_folds=6, scoring=r2_score):#'accuracy'):

    df_model_results = pd.DataFrame(columns=['Model','Mean','Std','cv_results', 'Data_size'])
    
    scorer = make_scorer(scoring)

    results = []
    names = []

    for name, model in models_list:
        kfold = KFold(n_splits=n_folds, shuffle=True)
        cv_results = cross_val_score(model, X, Y, cv=kfold, scoring=scorer)
        results.append(cv_results)
        names.append(name)
        # msg = "%s: %f (%f)" % (name, cv_results.mean(), cv_results.std())
        df_model_results.loc[len(df_model_results.index)] = [name, cv_results.mean(), cv_results.std(), cv_results, Data_size]
        # print(msg)

    return df_model_results


def get_split_data(num_splits):
        
    Data_new = pd.read_csv(f'../identification_of_critical_eigenvalues/{DI_method}_{data_number[-4:]}.csv').drop(['Unnamed: 0', 'case_id', 'Stability', 'Stable'], axis=1)
    Data_8464 = pd.read_csv(f'../identification_of_critical_eigenvalues/{DI_method}_8464.csv').drop(['Unnamed: 0', 'case_id', 'Stability'], axis=1)
    Data_combined = pd.concat([Data_new, Data_8464]).fillna(0)

    shuffled_data = np.random.permutation(Data_combined)  # Shuffle the data
    split_data = np.array_split(shuffled_data, num_splits)  # Split into 15 parts
    Data = [pd.DataFrame(part, columns = Data_combined.columns) for part in split_data]  
    for i in range(1, len(split_data)):
        Data[i] = pd.concat([Data[i-1],Data[i]])
        
    return Data

plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Palatino"],
})


DIs_used = ['DI_crit', 'DI_all']
highest_r2_methods = {}
for DI_method in DIs_used:    
    with open('../identification_of_critical_eigenvalues/data_number.json', 'r') as file:
        data_number = json.load(file)
    
    num_splits = 15
    Data = get_split_data(num_splits)
    Data_sizes = [i.shape[0] for i in Data]
    
    cumulative_r2_summary=pd.DataFrame()
    highest_r2_scores = pd.DataFrame(columns = ['data_size', 'method', 'mean_r2_score'])
    for i in range(len(Data)):
        #%% Remove correlated variables
        corr_matrix=abs(Data[i].corr())
        corr_matrix=corr_matrix.sort_values(by=DI_method,ascending=False)
        corr_matrix=corr_matrix.drop(DI_method,axis=0)
        uncorr_var=Data[i].columns
        
        for var in corr_matrix.index:
            if var not in corr_matrix.index:
                continue
            corrs=corr_matrix[[var]].drop(var,axis=0)
            corrs_var=corrs.query('{var}>=0.9'.format(var=var)).index
            uncorr_var=list(set(uncorr_var)-set(corrs_var))
            corr_matrix=corr_matrix.drop(corrs_var,axis=0)
           
        # split into test train 
        X = Data[i].drop(DI_method, axis=1)
        y=Data[i][DI_method]
        Xtrain, Xtest, ytrain, ytest = train_test_split(X, y, test_size=0.10, random_state=42)
        
        
        #%% Train MARS model
        
        # mars_model=Earth(feature_importance_type='gcv')#smooth=False, max_degree=2)
        # mars_model.fit(Xtrain,ytrain)
        
        # mars_summary = mars_model.summary()
        # feat_imp = mars_model.summary_feature_importances()
        
        # a_file=open('feature_importance.txt','w')
        # a_file.write(feat_imp[14:])
        # a_file.close()
        
        # feat_imp = pd.read_csv('feature_importance.txt',header=None)
        # feat_imp_df=pd.DataFrame()
        
        # for i in range(0,len(feat_imp)):
        #     feat_imp_df.loc[i, 'VAR'] = feat_imp.loc[i,0].split(' ')[0]
        
        # feat_imp_df['GCV'] = mars_model.feature_importances_
        
        # feat_imp_df = feat_imp_df.sort_values(by='GCV').reset_index(drop=True)
        
        # feat_imp_df.loc[0, 'cumulative'] = feat_imp_df.loc[0, 'GCV']
        
        # for ii in range(1, len(feat_imp_df)):
        #     feat_imp_df.loc[ii, 'cumulative'] = (feat_imp_df.loc[ii - 1, 'cumulative'] + feat_imp_df.loc[ii, 'GCV'])
        
        # feat_imp_df['cumulative'] = feat_imp_df['cumulative'] * 100
        
        # feat_imp_df = feat_imp_df.query('GCV!=0')
        # labels = list(feat_imp_df['VAR'])
        # fig = plt.figure(figsize=(5, 6))
        # ax = fig.add_subplot()
        # ax.scatter(feat_imp_df['cumulative'], np.arange(0, len(feat_imp_df)))
        # ax.set_yticklabels(labels)
        # #ax.yaxis.set_ticks(np.arange(0,len(labels)),labels)
        # ax.grid()
        # ax.set_title('GCV-based Features Importance \n GD-driven Case', fontsize=15)
        # ax.set_xlabel('Importance', fontsize=15)
        # fig.tight_layout()
        # fig.savefig('Feature_Importance.png')
        
        # %% train other models 
        
        models_list = ['LR','Lasso','Ridge','ElasticNet','DT','RF','MLP']
        models_dict={'LR': LinearRegression(),'Lasso': Lasso(alpha=0.01, max_iter=5000),'Ridge': Ridge(alpha=0.005),'ElasticNet': ElasticNet(),
                    'DT': DecisionTreeRegressor(),'RF':RandomForestRegressor(),'MLP':MLPRegressor(max_iter=5000)}
        models_tuple_list = [(name, models_dict[name]) for name in models_list]
        
        lin_model_trained={}
        
        for name in models_list:
            lin_model_trained[name] = models_dict[name].fit(Xtrain, ytrain)
            
        #%% calculate r2 scores 
        obj_func_ind=0
        for obj_fun in ['one_objective_function']: #['Min_P_SG','Min_P_losses']:
        
            # pred_mars=mars_model.predict(Xtest)
            # r2_mars=r2_score(ytest,pred_mars.reshape(-1,1))
            
            
            n_folds = 6
            r2_summary = compare_models(models_tuple_list, Xtrain, ytrain, Data_sizes[i], n_folds=n_folds, scoring=r2_score)
            print(r2_summary)
        
            # # r2_summary.loc[i,'Obj_Fun']=obj_fun
            # obj_func_ind=obj_func_ind+1
        
            
            highest_r2_scores.loc[i, 'data_size'] = Data_sizes[i]
            highest_r2_scores.loc[i,'mean_r2_score'] = r2_summary.loc[:,"Mean"].max()
            highest_r2_scores.loc[i,'method'] = r2_summary.loc[r2_summary.loc[:,"Mean"].idxmax(),"Model"]
            print(highest_r2_scores)
            
            cumulative_r2_summary = pd.concat([cumulative_r2_summary, r2_summary], ignore_index=True)
            print(cumulative_r2_summary)

    pd.DataFrame.to_csv(cumulative_r2_summary,f'R2_summary_{DI_method}.csv')
    pd.DataFrame.to_csv(highest_r2_scores,f'Highest_Scores_{DI_method}.csv')
    
    # plot the highest scores 
    fig = plt.figure(figsize=(5, 6))
    ax = fig.add_subplot()
    ax.scatter(highest_r2_scores['data_size'], highest_r2_scores['mean_r2_score'])
    ax.grid()
    ax.set_title(f'R2 Scores for {DI_method}', fontsize=15)
    ax.set_xlabel('Number of Values', fontsize=15)
    fig.tight_layout()
    # fig.savefig('.png')
    fig.show()

    highest_r2_methods[DI_method] = highest_r2_scores
    

# plot the graph with both DI generation methods 
fig = plt.figure(figsize=(5, 6))
ax = fig.add_subplot()
ax.scatter(highest_r2_methods['DI_crit']['data_size'], highest_r2_methods['DI_crit']['mean_r2_score'], label='DI Critical Eigs')
ax.scatter(highest_r2_methods['DI_all']['data_size'], highest_r2_methods['DI_all']['mean_r2_score'], label='DI All Eigs')
ax.grid()
# ax.set_title('R2 Scores', fontsize=15)
ax.set_xlabel('Number of Training Instances', fontsize=15)
ax.set_ylabel('R2 Scores of Regression Models', fontsize = 15)
ax.legend()
fig.tight_layout()
fig.savefig('R2_scores.png')
fig.show()




