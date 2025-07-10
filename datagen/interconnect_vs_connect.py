import control as ct
import pandas as pd
import time
# import numpy as np

#%% prova ct.interconnect: (control 0.10.0)
    
llista_sys=llista_SS_rl+llista_SS_C+llista_SS_nus
llista_sys=[llista_sys[0],llista_sys[165],llista_sys[166]]

llista_u=['ic_q1','ic_d1', 'ic_q2', 'ic_d2']
llista_y=['NET_iq_1_2', 'NET_id_1_2']

sys_interc=ct.interconnect(llista_sys, inputs=llista_u, outputs=llista_y)

'''
sys_interc.A
Out  [18]: 
array([[  -95.28554295,  -314.15926536,  3144.73739098,     0.        , -3144.73739098,     0.        ],
       [  314.15926536,   -95.28554295,     0.        ,  3144.73739098,     0.        , -3144.73739098],
       [    0.        ,     0.        ,     0.        ,  -314.15926536,     0.        ,     0.        ],
       [    0.        ,     0.        ,   314.15926536,     0.        ,     0.        ,     0.        ],
       [    0.        ,     0.        ,     0.        ,     0.        ,     0.        ,  -314.15926536],
       [    0.        ,     0.        ,     0.        ,     0.        ,   314.15926536,     0.        ]])

sys_interc.B
Out  [19]: 
array([[    0.        ,     0.        ,     0.        ,     0.        ],
       [    0.        ,     0.        ,     0.        ,     0.        ],
       [17347.2813561 ,     0.        ,     0.        ,     0.        ],
       [    0.        , 17347.2813561 ,     0.        ,     0.        ],
       [    0.        ,     0.        , 15280.11991046,     0.        ],
       [    0.        ,     0.        ,     0.        , 15280.11991046]])

sys_interc.C
Out  [4]: 
array([[1., 0., 0., 0., 0., 0.],
       [0., 1., 0., 0., 0., 0.]])

sys_interc.D
Out  [22]: 
array([[0., 0., 0., 0.],
       [0., 0., 0., 0.]])

sys_interc.state_labels
Out  [26]: ['sys[1]_iq_1_2', 'sys[1]_id_1_2', 'sys[0]_vc_q1', 'sys[0]_vc_d1', 'sys[4]_vc_q2', 'sys[4]_vc_d2']

'''

#%% write interconnect results

pd.DataFrame.to_csv(pd.DataFrame(PI_NET.A),'PI_NET_A.csv')
pd.DataFrame.to_csv(pd.DataFrame(PI_NET.B),'PI_NET_B.csv')
pd.DataFrame.to_csv(pd.DataFrame(PI_NET.C),'PI_NET_C.csv')
pd.DataFrame.to_csv(pd.DataFrame(PI_NET.D),'PI_NET_D.csv')

# open file in write mode
with open(r'PI_NET_state_labels.txt', 'w') as fp:
    for item in PI_NET.state_labels:
        # write each item on a new line
        fp.write("%s\n" % item)



llista_sys=llista_SS_rl+llista_SS_C+llista_SS_nus
llista_sys=[ct.StateSpace(llista_sys[0]),ct.StateSpace(llista_sys[165]),ct.StateSpace(llista_sys[166])]

llista_u=['ic_q1','ic_d1', 'ic_q2', 'ic_d2']
llista_y=['NET_iq_1_2', 'NET_id_1_2']

sys_app=ct.append(llista_sys[0],llista_sys[1],llista_sys[2])

llista_u_conc=llista_sys[0].input_labels+llista_sys[1].input_labels+llista_sys[2].input_labels
sys_app.input_labels=llista_u_conc

llista_y_conc=llista_sys[0].output_labels+llista_sys[1].output_labels+llista_sys[2].output_labels
sys_app.output_labels=llista_y_conc

llista_x_conc=llista_sys[0].state_labels+llista_sys[1].state_labels+llista_sys[2].state_labels
sys_app.state_labels=llista_x_conc


Q=[[2,5],[1,3],[3,4],[4,6]]

# TODO: Cambiado connect por interconnect. Recambiado
sys_conn = ct.connect(
    sys_app,
    Q,
    [5, 6, 7, 8],
    [1, 2]
)


'''
sys_conn.A
(Out  [50]): 
matrix([[  -95.28554295,  -314.15926536,  3144.73739098,     0.        , -3144.73739098,     0.        ],
        [  314.15926536,   -95.28554295,     0.        ,  3144.73739098,     0.        , -3144.73739098],
        [    0.        ,     0.        ,     0.        ,  -314.15926536,     0.        ,     0.        ],
        [    0.        ,     0.        ,   314.15926536,     0.        ,     0.        ,     0.        ],
        [    0.        ,     0.        ,     0.        ,     0.        ,     0.        ,  -314.15926536],
        [    0.        ,     0.        ,     0.        ,     0.        ,   314.15926536,     0.        ]])

sys_conn.B
(Out  [51]): 
matrix([[    0.        ,     0.        ,     0.        ,     0.        ],
        [    0.        ,     0.        ,     0.        ,     0.        ],
        [17347.2813561 ,     0.        ,     0.        ,     0.        ],
        [    0.        , 17347.2813561 ,     0.        ,     0.        ],
        [    0.        ,     0.        , 15280.11991046,     0.        ],
        [    0.        ,     0.        ,     0.        , 15280.11991046]])

sys_conn.C
(Out  [52]): 
matrix([[1., 0., 0., 0., 0., 0.],
        [0., 1., 0., 0., 0., 0.]])

sys_conn.D
(Out  [53]): 
matrix([[0., 0., 0., 0.],
        [0., 0., 0., 0.]])
'''



llista_sys=newsys.syslist
llista_sys=[ct.StateSpace(llista_sys[0]),ct.StateSpace(llista_sys[165]),ct.StateSpace(llista_sys[166])]

llista_u=['ic_q1','ic_d1', 'ic_q2', 'ic_d2']
llista_y=['NET_iq_1_2', 'NET_id_1_2']

sys_app=ct.append(llista_sys[0],llista_sys[1],llista_sys[2])

llista_u_conc=llista_sys[0].input_labels+llista_sys[1].input_labels+llista_sys[2].input_labels
sys_app.input_labels=llista_u_conc

llista_y_conc=llista_sys[0].output_labels+llista_sys[1].output_labels+llista_sys[2].output_labels
sys_app.output_labels=llista_y_conc

llista_x_conc=llista_sys[0].state_labels+llista_sys[1].state_labels+llista_sys[2].state_labels
sys_app.state_labels=llista_x_conc


llista_u_2conn=list(set(llista_u_conc)-set(llista_u))
sys_inp_indx=[sys_app.input_index[u]+1 for u in llista_u_2conn]

sys_out_indx=[sys_app.output_index[y]+1 for y in llista_u_2conn]

Q = list(zip(sys_inp_indx, sys_out_indx))

# TODO: Cambiado connect por interconnect. Recambiado
sys_conn = ct.connect(
    sys_app,
    Q,
    [sys_app.input_index[u] + 1 for u in llista_u],
    [sys_app.output_index[y] + 1 for y in llista_y]
)

'''
sys_conn.A
Out  [81]: 
matrix([[  -95.28554295,  -314.15926536,  3144.73739098,     0.        , -3144.73739098,     0.        ],
        [  314.15926536,   -95.28554295,     0.        ,  3144.73739098,     0.        , -3144.73739098],
        [    0.        ,     0.        ,     0.        ,  -314.15926536,     0.        ,     0.        ],
        [    0.        ,     0.        ,   314.15926536,     0.        ,     0.        ,     0.        ],
        [    0.        ,     0.        ,     0.        ,     0.        ,     0.        ,  -314.15926536],
        [    0.        ,     0.        ,     0.        ,     0.        ,   314.15926536,     0.        ]])

sys_conn.B
Out  [82]: 
matrix([[    0.        ,     0.        ,     0.        ,     0.        ],
        [    0.        ,     0.        ,     0.        ,     0.        ],
        [17347.2813561 ,     0.        ,     0.        ,     0.        ],
        [    0.        , 17347.2813561 ,     0.        ,     0.        ],
        [    0.        ,     0.        , 15280.11991046,     0.        ],
        [    0.        ,     0.        ,     0.        , 15280.11991046]])

sys_conn.C
Out  [83]: 
matrix([[1., 0., 0., 0., 0., 0.],
        [0., 1., 0., 0., 0., 0.]])

sys_conn.D
Out  [84]: 
matrix([[0., 0., 0., 0.],
        [0., 0., 0., 0.]])
'''



llista_sys=newsys.syslist
llista_u= newsys.input_labels
llista_y= newsys.output_labels

start=time.time()
sys_interc=ct.interconnect(llista_sys, inputs=llista_u, outputs=llista_y)
end=time.time()
time_interc=end-start
print('time_inteconnect',time_interc)

llista_sys=[ct.StateSpace(s) for s in llista_sys]

start=time.time()

sys_app=[]
llista_u_conc=[]
llista_y_conc=[]
llista_x_conc=[]

for s in llista_sys:
    sys_app=ct.append(sys_app,s)

    llista_u_conc.extend(s.input_labels)
    llista_y_conc.extend(s.output_labels)
    llista_x_conc.extend(s.state_labels)

sys_app.input_my_labels=llista_u_conc

sys_app.output_my_labels=llista_y_conc

sys_app.state_my_labels=llista_x_conc

llista_u_2conn=list(set(llista_u_conc)-set(llista_u))

# sys_inp_indx=[np.where(np.array(sys_app.input_my_labels)==u)[0]+1 for u in llista_u_2conn]
sys_inp_indx=[]
for u in llista_u_2conn:
        sys_inp_indx.extend(np.where(np.array(sys_app.input_my_labels)==u)[0]+1)
        
# =[sys_app.output_my_labels.index(y)+1 for y in llista_u_2conn]
sys_out_indx=[]
for y in llista_u_2conn:
        n_inp=len(np.where(np.array(sys_app.input_my_labels)==y)[0]+1)
        sys_out_indx.extend(np.ones([n_inp,])*np.where(np.array(sys_app.output_my_labels)==y)[0]+1)
        

Q = list(zip(sys_inp_indx, sys_out_indx))

# uu_idx=[np.sys_app.input_my_labels.index(u)+1 for u in llista_u]
# yy_idx=[sys_app.output_my_labels.index(y)+1 for y in llista_y]

uu_idx=[]
for u in llista_u:
        uu_idx.extend(np.where(np.array(sys_app.input_my_labels)==u)[0]+1)

yy_idx=[]
for y in llista_y:
        yy_idx.extend(np.where(np.array(sys_app.output_my_labels)==y)[0]+1)

# TODO: Cambiado connect por interconnect. Recambiado
sys_conn = ct.connect(sys_app, Q, uu_idx, yy_idx)


end=time.time()
time_conn=end-start
print('time_connect',time_conn)

# PI_NET_A_interc=pd.read_csv('PI_NET_A.csv')
# PI_NET_B_interc=pd.read_csv('PI_NET_B.csv')
# PI_NET_C_interc=pd.read_csv('PI_NET_C.csv')
# PI_NET_D_interc=pd.read_csv('PI_NET_D.csv')

PI_NET_A_interc=sys_interc.A
PI_NET_B_interc=sys_interc.B
PI_NET_C_interc=sys_interc.C
PI_NET_D_interc=sys_interc.D


diff_A=sys_conn.A-np.array(PI_NET_A_interc)#[:,1:]
diff_B=sys_conn.B-np.array(PI_NET_B_interc)#[:,1:]
diff_C=sys_conn.C-np.array(PI_NET_C_interc)#[:,1:]
diff_D=sys_conn.D-np.array(PI_NET_D_interc)#[:,1:]

print(diff_B.sum())

# diff_A=np.where(sys_conn.A!=np.array(PI_NET_A_interc)[:,1:])
# diff_C=np.where(sys_conn.C!=np.array(PI_NET_C_interc)[:,1:])
# diff_B=np.where(sys_conn.B!=np.array(PI_NET_B_interc)[:,1:])
# diff_D=np.where(sys_conn.D!=np.array(PI_NET_D_interc)[:,1:])

#%%