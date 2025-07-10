%% CLEAR WORKING ENVIRONMENT and SET PATHS

clearvars 
clc
close all
path(pathdef)
addpath(genpath(pwd))

%% SET INPUT DATA

% Case name as in Excel files
    caseName = './01_data/cases/NREL_seed16/IEEE118_FULL'; 
    % caseName_2 = './01_data/cases/seed17_GFOL_RL_percgfor091_PyStable/IEEE118_FULL'; 

% Relative path to the Folder for storing results
    path_results = '02_results\'; 

% Set power-flow source (0: Excel, 1: Fanals, 2: MATACDC) 
    fanals = 0; 

% Flag to indicate if T_case should be used (REE)
    shared_power = 0;

%% READ GRID TOPOLOGY DATA
 
% Create excel files and simulink models names 
    run set_file_names.m

% Read excel file and generate tables of grid elements
    run read_data.m

    T_SG.Vn=T_SG.Vn/1e3;
    T_VSC.Vn=T_VSC.Vn/1e3;

    % excel_2    = [caseName_2 '.xlsx']; 
    % T_SG_2     = readtable(excel_2,'Sheet','SG');            %SG table
    % T_SG.exc(:)=T_SG_2.exc(1)
% Clean input data
    run preprocess_data.m

%% POWER-FLOW
 
% Update state of switches (open/close lines)
    set_breaker_state('line',1,'close')

% Get Power-Flow results
    run PF_results.m;

% Update operation point of generator elements
    % run update_OP.m
        
%% READ PARAMETERS DATA

% Get parameters of generator units from excel files & compute pu base
    run get_parameters.m

% Compute reference angle (delta_slk)
    run delta_slack.m

%% GENERATE STATE-SPACE MODEL

% Generate AC & DC NET State-Space Model
    %run generate_NET.m 
    run generate_NET_with_Qneg.m
% Generate generator units State-Space Model
    run generate_elements.m

%% BUILD FULL SYSTEM STATE-SPACE MODEL

% Display and select all global input & outputs
    run display_io.m  
    ss_sys = connect(l_blocks{:}, input, output);

% % or ... Display only variables in specified buses 
%     bus_in   = 12; %bus to apply disturbance
%     user_out =  [];
%     th_out   = [];
%     load_out = [12 14];
%     sg_out = [12 19];
%     vsc_out = [12 19];    
%     run display_io_reduced.m
%     ss_sys = connect(l_blocks{:}, input, output);

%% NON-LINEAR


%% SMALL-SIGNAL ANALYSIS

% Eigenvalues
    T_EIG   = FEIG(ss_sys,[0.25 0.25 0.25],'o',false)
    %head(T_EIG)

    % Export T_EIG to excel
    % writetable(T_EIG, [path_results caseName '_EIG.xlsx'])

    % Save eigenavalue map figure
    % T_EIG   = FEIG(ss_sys,[0.25 0.25 0.25],'o',true); 
    % exportgraphics(gcf,[path_results caseName 'EIG.emf'])


% Participation factors
    % % Obtain all participation factors
    % T_modal = FMODAL(ss_sys);
    % % Save participation factors map figrue
    % % exportgraphics(gcf,[path_results caseName '_pf.emf'])
    % 
    % % Obtain the participation factors for the selected modes
    % FMODAL_REDUCED(ss_sys,[1,2]); 

    % Obtain the participation factors >= x, for the selected mode
    FMODAL_REDUCED_th(ss_sys,[1:15], 0.2);     


% % Initialization
% 
%     run NET_initialization.m
% 
% % Create simulink nonlinear model
% 
%     if ~isfile(['00_tool/Non Linear Models/models/' nonlinear '.slx'])
%         run NET_layout_FORCE.m % create simulink nonlinear model
%          newSys = 1;
%     else
%         open(nonlinear) % open already existing model
%         newSys = 0;
%     end
% 
% % Avoid redundant initialization
%     run dependent_states.m
% 
% % Set disturbance
%     run param_nonlinear.m
% 
% % Simulate
%     out_nolin = sim(nonlinear);  
% 
%     MsgBoxH = findall(0,'Type','figure','Name','Initial state conflict');
%     close(MsgBoxH);
% 
% %% LINEAR MODEL
% 
% % Set Linear Simulation parameters
%     run param_linear.m
% 
% % Create simulink linear model
%     if ~isfile(['00_tool/Linear Model/models/' linear '.slx'])
%         generate_linear(ss_sys,linear,tstep_lin,Tsim_lin,delta_u) % create simulink linear model
%     else
%         open(linear) % open already existing model       
%     end
% 
% % Simulate
%     out_lin = sim(linear); 

%% VALIDATE LINEAR MODEL

% run validate_linear.m