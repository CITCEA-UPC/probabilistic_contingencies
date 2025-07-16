import pandas as pd
import numpy as np
import random


def random_operating_point(d_op,d_raw_data, GridCal_grid,n_reg=1,loads_power_factor=0.95, generators_power_factor=0.95, all_gfor=False, fix_seed=False):
    Pd=random_demand(list(d_op['Demand'].MinLoad),list(d_op['Demand'].PeakLoad),n_reg,fix_seed)
    
    d_raw_data = assign_loads_to_d_raw_data(d_raw_data, d_op, n_reg, loads_power_factor,Pd)
    
    Pg=np.sum(Pd)

    n_gen=len(d_raw_data['generator'])    
    
    d_raw_data=assign_gens_to_d_raw_data(d_raw_data, d_op, n_gen, generators_power_factor, Pg,fix_seed)
    
    d_raw_data = assign_P_by_CIG_and_SG(d_raw_data, d_op, n_gen)
    
    d_raw_data, d_op = assign_Snom_GFOL_GFOR(d_raw_data, d_op, GridCal_grid, n_gen, all_gfor)
    
    d_raw_data = alphas_P(d_raw_data)
    
    return d_raw_data, d_op

    

def random_demand(Pd_min,Pd_max,n_reg,fix_seed=False):
    if fix_seed:
        random.seed(10)

    pi=random.uniform(0, 1)
    
    Pd=[]

    for p in range(0,n_reg):
        Pd.append(pi*(Pd_max[p]-Pd_min[p])+Pd_min[p])
    
    return Pd

def assign_loads_to_d_raw_data(d_raw_data,d_op,n_reg,loads_power_factor,Pd):
    for r in range(1,n_reg+1):
        pf=np.array(d_op['Loads'].query('Region == @r')['Load_Participation_Factor'])
        d_raw_data['load'].loc[d_raw_data['load'].query('Region == @r').index,'PL']=Pd[r-1]*pf
        
        d_raw_data['load']['P']=d_raw_data['load']['PL']/100
        
    d_raw_data['load']['QL']=d_raw_data['load']['PL']*np.sqrt(1-loads_power_factor**2)/loads_power_factor
    d_raw_data['load']['Q']=d_raw_data['load']['P']*np.sqrt(1-loads_power_factor**2)/loads_power_factor
    
    return d_raw_data

def assign_gens_to_d_raw_data(d_raw_data,d_op,n_gen,generators_power_factor,Pg,fix_seed=False):
    if fix_seed:
        np.random.seed(10)
    # gamma= np.random.dirichlet(np.ones(n_gen))
    # Pg_i=Pg*gamma
    # Pg_tot_i=np.array(d_op['Generators']['Pmax'])
    # ind_all=np.arange(0,n_gen)
    # while any(Pg_tot_i<Pg_i):
    #     ind=np.where(Pg_tot_i<Pg_i)[0]
    #     P_exc=0
    #     for i in ind:
    #         P_delta=Pg_i[i]-Pg_tot_i[i]
    #         P_exc=P_exc+P_delta
    #         Pg_i[i]=Pg_tot_i[i]
    #     ind_non_exc=list(set(ind_all)-set(ind))
    #     Pg_i[ind_non_exc]=Pg_i[ind_non_exc]+P_exc/len(ind_non_exc)
    #     ind_all=list(set(ind_all)-set(ind))
    
    Pg_i=get_cases_extreme(d_op, Pg)
    
    d_raw_data['generator']['PG']=Pg_i
    d_raw_data['generator']['QG']=Pg_i*np.sqrt(1-generators_power_factor**2)/generators_power_factor
       
    return d_raw_data

def assign_P_by_CIG_and_SG(d_raw_data, d_op, n_gen,fix_seed=False):
    if fix_seed:
       np.random.seed(10)
    alpha=np.random.random((n_gen,1)) # percentage of P injected by CIG
    
    alpha_max=np.ones([n_gen,1])
    alpha_max[d_op['Generators'].query('Pmax_CIG == 0').index]=0
    alpha_max[np.where(d_op['Generators']['Pmax_CIG']>d_raw_data['generator']['PG']),0]=d_raw_data['generator'].loc[np.where(d_op['Generators']['Pmax_CIG']>d_raw_data['generator']['PG']),'PG']/d_op['Generators'].loc[np.where(d_op['Generators']['Pmax_CIG']>d_raw_data['generator']['PG']),'Pmax_CIG']
    
    alpha=alpha_max[:,0]*alpha[:,0]
        
    d_raw_data['generator'][['P_CIG']]=d_op['Generators'][['Pmax_CIG']]*alpha.reshape(-1,1)
    d_raw_data['generator']['P_SG']=d_raw_data['generator']['PG']-d_raw_data['generator']['P_CIG']
    # print(any(d_raw_data['generator']['P_CIG']>d_op['Generators']['Pmax_CIG']))
    # print(any(d_raw_data['generator']['P_SG']>d_op['Generators']['Pmax_SG']))
    # print(any(d_raw_data['generator']['P_SG']<0))
    
    if any(d_raw_data['generator']['P_SG']>d_op['Generators']['Pmax_SG']):
        excess_sg=d_raw_data['generator']['P_SG']>d_op['Generators']['Pmax_SG']
        ind=excess_sg[excess_sg].index
        delta=d_raw_data['generator'].loc[ind,'P_SG']-d_op['Generators'].loc[ind,'Pmax_SG']
        d_raw_data['generator'].loc[ind,'P_CIG']=d_raw_data['generator'].loc[ind,'P_CIG']+delta
        d_raw_data['generator'].loc[ind,'P_SG']=d_raw_data['generator'].loc[ind,'P_SG']-delta
        
    # print(any(d_raw_data['generator']['P_SG']>d_op['Generators']['Pmax_SG']))
    
    return d_raw_data

def assign_Snom_GFOL_GFOR(d_raw_data, d_op, GridCal_grid, n_gen, all_gfor):
                    
    buses=GridCal_grid.get_buses()
    for bus in buses:
        if bus.determine_bus_type()._value_ == 3 :
            
            slack_bus_name=bus._name
            break
    
    if all_gfor:    
        beta=np.ones([n_gen,1])
    else:
        beta=np.random.random((n_gen,1))
        ind_slack=d_op['Generators'].query('BusName == @slack_bus_name').index[0]
        beta[ind_slack]=1
    
    d_raw_data['generator']['P_GFOR']=d_raw_data['generator']['P_CIG']*beta.ravel()
    d_op['Generators']['Snom_GFOR']= d_op['Generators']['Pmax_CIG']*beta.ravel()/0.8
    
    d_raw_data['generator']['P_GFOL']=d_raw_data['generator']['P_CIG']-d_raw_data['generator']['P_GFOR']
    d_op['Generators']['Snom_GFOL']= d_op['Generators']['Pmax_CIG']*(1-beta.ravel())/0.8
    
    return d_raw_data, d_op

def alphas_P(d_raw_data):
    for el in ['SG','GFOR','GFOL']:
        d_raw_data['generator']['alpha_P_'+el]=d_raw_data['generator']['P_'+el]/d_raw_data['generator']['PG']
        
    return d_raw_data
            
def get_cases_extreme(d_op, sample, generator = np.random.default_rng(seed=10) , iter_limit=5000,
                          iter_limit_variables=500):
        """This case generator aims to reach more variance between cases within
        a sample. Here, we assign random values to de variable_borders in the range
        lower bound of this variable - minimum between upper bound of the
        variable and remaining sum, so that we never exceed sample.

        Once every variable has value, we will add to it a random value
        between this value and the maximum possible value (explained above)
        until error is less than defined (dimension tolerance).

        :param generator:
        :param sample: Target sum
        :param iter_limit: Maximum number of iterations. Useful to avoid
            infinite loops
        :param iter_limit_variables: Maximum number of iterations to go over
            all variable_borders again and distribute the remaining sum
        :return: Combinations of n_cases variable_borders that, when summed together,
            equal sample. If the combination cannot not be found with the
            defined iter_limit, this case will be filled with NaN values.
        """
        # Distribute remaining sum within variable_borders
        # Shuffle variable_borders
        cases = []
        iters_cases = 0
        max_val = sum([v for v in list(d_op['Generators']['Pmax'])])
        min_val = sum([v for v in list(d_op['Generators']['Pmin'])])

        if not (max_val >= sample >= min_val):
            raise ValueError(f"Sample {sample} cannot be reached by ")
                             # f"dimension {self.label}, with variable_borders borders "
                             # f"{self.variable_borders}")

        # while len(cases) < self.n_cases and iters_cases < iter_limit:
        while iters_cases < iter_limit:
            iters_cases += 1
            initial_case = np.array(d_op['Generators']['Pmin']).ravel()
            case = initial_case.copy()
            total_sum = sum(case)
            iters_variables = 0
            while (not np.isclose(total_sum, sample) and
                   iters_variables < iter_limit):
                indexes = list(range(len(d_op['Generators']['Pmin'])))
                generator.shuffle(indexes)

                iters_variables += 1
                for i in indexes:
                    if np.isclose(total_sum, sample):
                        break
                    new_var = generator.uniform(case[i],
                                                np.array(d_op['Generators']['Pmax']).ravel()[i])
                    new_var = np.clip(new_var, case[i],
                                      case[i] + sample - total_sum)
                    case[i] = new_var
                    total_sum = sum(case)

            if iters_variables >= iter_limit_variables:
                print(f"Warning: sample {sample} couldn't be reached"
                      f" by total sum {total_sum}) in case {case}")
                continue
            if np.isclose(total_sum, sample):
                cases.append(case)
        # if iters_cases >= iter_limit:
        #     print("Warning: Iterations count exceeded. "
        #           "Retrying with normal sampling")
        #     return get_cases_normal(sample, generator)

        return cases[-1]

def get_cases_normal(d_op, sample, generator = np.random.default_rng(seed=10), iter_limit_factor=1000):
    """
    Generate `n_cases` number of random cases for the given sample.

    The cases are generated using normal distribution with means obtained
    from distributing the sample value over the different values in a
    proportional way with respect to their ranges (lower/upper bounds).

    The standard deviation of each variable is selected so that there is a
    probability of 99 % of a new point lying inside the variable range.

    :param generator:
    :param sample: A random input value representing the dimension, with
        the requirement that the different variable_borders of the dimension
        must collectively sum up to it.
    :param iter_limit_factor: Factor to multiply for the maximum number of
        iterations
    :return cases: Array of the generated cases
    """
    cases = []
    # Perform scaling
    var_avg = ((self.variable_borders[:, 1] - self.variable_borders[:, 0]) / 2
               + self.variable_borders[:, 0])
    avg_sum = var_avg.sum()
    alpha = sample / avg_sum
    scaled_avgs = var_avg * alpha
    stds = []
    # Perform scaling
    for i in range(len(self.variable_borders)):
        d_min = min(abs(self.variable_borders[i][0] - scaled_avgs[i]),
                    abs(self.variable_borders[i][1] - scaled_avgs[i]))
        # Initialize standard deviations
        stds.append(d_min / 3)
    iters = 0
    iter_limit = len(self.variable_borders) * self.n_cases * iter_limit_factor
    max_val = sum([v[1] for v in self.variable_borders])
    min_val = sum([v[0] for v in self.variable_borders])

    if not (max_val >= sample >= min_val):
        raise ValueError(f"Sample {sample} cannot be reached by "
                         f"dimension {self.label}, with variable_borders borders "
                         f"{self.variable_borders}")

    while len(cases) < self.n_cases and iters < iter_limit:
        case = generator.normal(scaled_avgs, stds)
        lower_bounds = self.variable_borders[:, 0]
        upper_bounds = self.variable_borders[:, 1]
        case = np.clip(case, lower_bounds, upper_bounds)
        case_sum = case.sum()
        if self.borders[0] < case_sum < self.borders[1]:
            cases.append(case)
        else:
            print(f"get_cases_normal: Iteration {iters + 1}")
            print(f"Warning: (label {self.label}) Case sum {case_sum} out "
                  f"of dimension borders {self.borders} in {case} for "
                  f"sample {sample}. Retrying...")
        iters += 1
    print(f"Dim {self.label}: get_cases_normal run {iters} iterations.")

    while len(cases) < self.n_cases:
        print(f"Warning: Dim {self.label} - get_cases_normal exhausted "
              f"iterations: {iters} iterations.")
        print("Adding NaN cases")
        cases.append([np.nan] * len(self.variable_borders))

    return cases   
 
 
 