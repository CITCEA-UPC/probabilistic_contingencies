%% CLEAR WORKING ENVIRONMENT and SET PATHS

close all;
clearvars 
clc
path(pathdef)
addpath(genpath(pwd))

%% SET INPUT DATA

% Case name as in Excel files
    caseName =  '/TestDyn_4CIGs/OP_7'%'test_MPC'; %
    caseNameNLin =  eraseBetween(regexprep(caseName,{'/'},{'_'}),1,1);%'test_MPC'; %
    caseNameLin =  caseNameNLin;%'OP_7'%'test_MPC'; %

% Relative path to the Folder for storing results
    path_results = '02_results\'; 

% Set power-flow source (0: Excel, 1: Fanals, 2: MATPOWER, 3: MATACDC) 
    fanals = 0; 

% Flag to indicate if T_case should be used (REE)
    shared_power = 0;

%% READ GRID TOPOLOGY DATA
 
% Create excel files and simulink models names 
    run set_file_names.m

% Read excel file and generate tables of grid elements
    run read_data.m

% Clean input data
    run preprocess_data.m

%% READ PARAMETERS DATA

% Get parameters of generator units from excel files & compute pu base
    run get_parameters.m

%% POWER-FLOW
 
% Update state of switches (open/close lines)
    set_breaker_state('line',1,'close')

% Get Power-Flow results
    run PF_results.m;

% Update operation point of generator elements
    run update_OP.m

% Compute reference angle (delta_slk)
    run delta_slack_acdc.m
        
%% GENERATE STATE-SPACE MODEL

% Generate AC & DC NET State-Space Model
    run generate_NET_with_Qneg.m
% Generate generator units State-Space Model
    run generate_elements.m

%% BUILD FULL SYSTEM STATE-SPACE MODEL

% Display and select all global input & outputs
    run display_io.m  
    %input = {'NET.Rld2'};
    %output = {'DC_NET.v1DC','DC_NET.v2DC', 'IPC1.idiffd' ,'IPC1.idiffq' ,'IPC1.w' ,'IPC2.idiffd' ,'IPC2.idiffq' ,'IPC2.w' ,...
    %          'Load1.id' ,'Load1.iq' ,'Load2.id' ,'Load2.iq' ,'NET.id_1_2' ,'NET.id_3_4' ,...
    %          'NET.iq_1_2' ,'NET.iq_3_4' ,'NET.vn1d' ,'NET.vn1q' ,'NET.vn2d' ,'NET.vn2q' ,...
    %          'NET.vn3d' ,'NET.vn3q' ,'NET.vn4d' ,'NET.vn4q' ,'SG1.id' ,'SG1.iq' ,'S2.id' ,'TH2.iq'};
    ss_sys = connect(l_blocks{:}, input, output);
%input = {'TH1.vq'};
%output = {'NET.vn1q' , 'NET.vn1d' , 'NET.vn2q' , 'NET.vn2d' , 'NET.vn3q' , 'NET.vn3d' , 'NET.vn4q' , 'NET.vn4d'};
% % or ... Display only variables in specified buses 
%     bus_in   = 12; %bus to apply disturbance
%     user_out =  [];
%     th_out   = [];
%     load_out = [12 14];
%     sg_out = [12 19];
%     vsc_out = [12 19];    
%     run display_io_reduced.m
%     ss_sys = connect(l_blocks{:}, input, output);


%% SMALL-SIGNAL ANALYSIS
% 
% Eigenvalues
     T_EIG   = FEIG(ss_sys,[0.25 0.25 0.25],'o',true)
%     %head(T_EIG)
% 
%     % Export T_EIG to excel
%     % writetable(T_EIG, [path_results caseName '_EIG.xlsx'])
% 
%     % Save eigenavalue map figure
%     % T_EIG   = FEIG(ss_sys,[0.25 0.25 0.25],'o',true); 
%     % exportgraphics(gcf,[path_results caseName 'EIG.emf'])
% 
% 
% Participation factors
%     % Obtain all participation factors
     T_modal = FMODAL(ss_sys);
%     % Save participation factors map figrue
%     % exportgraphics(gcf,[path_results caseName '_pf.emf'])
% 
%     % Obtain the participation factors for the selected modes
     % FMODAL_REDUCED(ss_sys,[1,2,3,4]); 
% 
%     % Obtain the participation factors >= x, for the selected mode
%     %FMODAL_REDUCED_th(ss_sys,[1,2,4], 0.2);     
% 

 %% NON-LINEAR

 % Replace all 'GFOL' with 'GFOL_LR'
 T_VSC.mode(strcmp(T_VSC.mode, 'GFOL')) = {'GFOL_RL'};

    if ~isfile(['00_tool/Non Linear Models/models/' nonlinear '.slx'])
        newSys = 1;
    else
        newSys = 0;
    end
% Initialization

     run NET_initialization.m

% Create simulink nonlinear model

    if newSys
        if fanals==3
            run NET_layout_FORCE_ACDC0.m % create AC/DC simulink nonlinear model 
        else
            run NET_layout_FORCE.m % create simulink nonlinear model
        end
    else
        open(nonlinear) % open already existing model
    end

% Avoid redundant initialization
    run dependent_states.m

% Set disturbance
    run param_nonlinear.m

% Simulate
    out_nolin = sim(nonlinear);  

    MsgBoxH = findall(0,'Type','figure','Name','Initial state conflict');
    close(MsgBoxH);

%% LINEAR MODEL

% Set Linear Simulation parameters
     run param_linear.m

% Create simulink linear model
     if ~isfile(['00_tool/Linear Model/models/' linear '.slx'])
         generate_linear(ss_sys,linear,tstep_lin,Tsim_lin,delta_u) % create simulink linear model
     else
         open(linear) % open already existing model       
     end

% Simulate

     %simConfig.Solver = "ode1";
     %simConfig.StopTime = "Tsim_lin";
     %simConfig.FixedStep="1e-08";
     %out_lin = sim(linear,simConfig); 
     out_lin = sim(linear); 

%% VALIDATE LINEAR MODEL

run validate_linear.m

