function mpc = parse_excel2mpc(shared_power)

    % Generate MATPOWER mpc from Excel file
    
    % Input data used from Excel file:
        % T_PF: buses, V, theta
        % T_XX: P,Q (V,theta from T_PF)
        % bus type is set automatically but can be changed manually by running:
        %   bus = change_bus_type(bus);
    
    % RELEVANT NOTES:
        % - Loads are "fixed" in the tool and therefore are added to bus data
        % - Transformers in the tool are equivalent to RX lines and therefore are added to branch data
        % - ACDC powerflow option to be implemented
        % - Only one load per bus

    % Import global variables names
    setup_globals; 

    % ---------------------------------------------------------------------
    % CASE IDENTIFICATION DATA 
    % ---------------------------------------------------------------------
    baseMVA = T_global.Sb_MVA(1);
    disp(['System power base is ' num2str(baseMVA) 'MVA'])

    
    % ---------------------------------------------------------------------
    % BUS DATA
    % ---------------------------------------------------------------------

    % Convert X,B columns to R,L 
    [T_NET,T_trafo,T_load,T_TH] = xb2lc(T_NET,T_trafo,T_load,T_TH,T_global.f_Hz);   
    % Generates the Connectivity Matrix and the Table of nodes for the AC grid:
    [connect_mtx, ~, ~, T_nodes] = generate_general_connectivity_matrix(T_NET,T_trafo, T_load, T_TH, T_SG, T_STATCOM, T_VSC, T_MMC_Pac_GFll,T_MMC_Vdc_GFll, T_b2b, T_user);
    
    bus_max = max([T_NET.bus_from; T_NET.bus_to; T_trafo.bus_from; T_trafo.bus_to; T_DC_NET.bus_from; T_DC_NET.bus_to]);
    nb = height(T_PF);
    bus = zeros(nb, 17); 
    
    % 1) BUS_I bus number (positive integer)
    bus(:,1) = T_PF.bus; 
    
    % 2) BUS_TYPE bus type (1 = PQ, 2 = PV, 3 = ref, 4 = isolated)
    for idx = 1:height(bus)     
        busNum = bus(idx,1);
         % If it is the slack --> ref
        if ismember(busNum, T_global.ref_bus)
            bus(idx,2) = 3;
        % If there is a generator --> PV (force Pv if there is a generator)
        elseif any(contains(T_nodes{T_nodes.Node == busNum,:},["TH", "SG", "VSC", "user"])) 
            bus(idx,2) = 2;
        % If there is a load --> PQ 
        elseif any(contains(T_nodes{T_nodes.Node == busNum,:},"Load")) 
            bus(idx,2) = 1;  
        % If it is connected to something 
        elseif any(connect_mtx(busNum,:)) 
            bus(idx,2) = 1;  
        % Isolated (if I set to 4, powerflow may not converge)
        else 
            bus(idx,2) = 4;
            disp(['Bus ' num2str(bus(idx,1)) ' is isolated. If power-flow does not converge, try setting them to PQ.'])
        end
    end
    
    % 3) PD real power demand (MW) --> initialized to zero, filled with PQ loads
    % 4) QD reactive power demand (MVAr) --> initialized to zero, filled with PQ loads
    if ~isempty(T_load)
        for idx = 1:height(bus)          
            if T_load{T_load.bus == bus(idx,1),"type"} == "PQ"
               bus(idx,3) = T_load{T_load.bus == bus(idx,1),"P"}*baseMVA; 
               bus(idx,4) = T_load{T_load.bus == bus(idx,1),"Q"}*baseMVA; 
            end
        end
    end
    
    % 5) GS shunt conductance (MW demanded at V = 1.0 p.u.) --> initialized to zero, filled with RX loads
    % 6) BS  shunt susceptance (MVAr injected at V = 1.0 p.u.) --> initialized to zero, filled with RX loads
    if ~isempty(T_load)
        for idx = 1:height(bus)          
            if T_load{T_load.bus == bus(idx,1),"type"} == "RX"
                if T_load{T_load.bus == bus(idx,1),"R"}
                    bus(idx,5) = 1/T_load{T_load.bus == bus(idx,1),"R"}*baseMVA; 
                end
                if T_load{T_load.bus == bus(idx,1),"X"}
                    bus(idx,6) = -1/T_load{T_load.bus == bus(idx,1),"X"}*baseMVA; 
                end
            end
        end
    end
    
    % 7) BUS_AREA area number (positive integer)   
    if any(strcmp('Area',T_PF.Properties.VariableNames)) %if column Area in T_PF
        for idx = 1:height(bus)      
            bus(idx,7) = T_PF{T_PF.bus == bus(idx,1),"Area"};
        end
    else
        bus(:,7) = ones(nb,1); %set Area=1 as default
    end
    
    % 8) VM voltage magnitude (p.u.)
    % 9) VA voltage angle (degrees)
    bus(:,8) = T_PF{T_PF.bus == bus(:,1), "Vm"}; %initialize with data in T_PF
    bus(:,9) = T_PF{T_PF.bus == bus(:,1), "theta"}; %initialize with data in T_PF
    
    % 10) BASE_KV base voltage (kV)
    for idx = 1:height(bus)        
        bus(idx,10) = T_global{T_global.Area == bus(idx,7),"Vb_kV"};
    end
    
    % 11) ZONE  loss zone (positive integer)
    bus(:,11) = ones(nb,1); %set Zone=1 as default
    
    % 12) VMAX maximum voltage magnitude (p.u.)
    bus(:,12) = 1.1*ones(nb,1); %default 1.1 pu
    
    % 13) VMIN minimum voltage magnitude (p.u.)
    bus(:,13) = 0.9*ones(nb,1); %default 0.9 pu
    
    % 14) LAM_P Lagrange multiplier on real power mismatch (u/MW) --> OPF
    % 15) LAM_Q  Lagrange multiplier on reactive power mismatch (u/MVAr) --> OPF
    % 16) MU_VMAX Kuhn-Tucker multiplier on upper voltage limit (u/p.u.) --> OPF
    % 17) MU_VMIN Kuhn-Tucker multiplier on lower voltage limit (u/p.u.) --> OPF
    
    % ---------------------------------------------------------------------
    % BRANCH DATA
    % ---------------------------------------------------------------------
    
    T_lines = [T_NET;  T_trafo(:,T_NET.Properties.VariableNames)];
    branch = zeros(height(T_lines),21);
    
    % 1) F_BUS "from" bus number
    branch(:,1) = T_lines.bus_from;
    
    % 2) T_BUS "to" bus number
    branch(:,2) = T_lines.bus_to;
    
    % 3) BR_R resistance (p.u.)
    branch(:,3) = T_lines.R;
    
    % 4) BR_X reactance (p.u.)
    branch(:,4) = T_lines.X;
    
    % 5) BR_B total line charging susceptance (p.u.)
    branch(:,5) = T_lines.B;
    
    % 6) RATE_A MVA rating A (long term rating), set to 0 for unlimited
    % 7) RATE_B MVA rating B (short term rating), set to 0 for unlimited
    % 8) RATE_C MVA rating C (emergency rating), set to 0 for unlimited
    
    % 9) TAP transformer off nominal turns ratio, if non-zero 
    
        % (taps at "from" bus, impedance at "to" bus,  i.e. if r = x = b = 0, tap = Vf/Vt)
        % tap = 0 used to indicate transmission line rather than transformer,
        % i.e. mathematically equivalent to transformer with tap = 1
    
    % 10)  SHIFT transformer phase shift angle (degrees), positive ⇒ delay
    
    % 11) BR_STATUS initial branch status, 1 = in-service, 0 = out-of-service
    branch(:,11) = T_lines.state;
    
    % 12) ANGMIN minimum angle difference, θf − θt (degrees)
    % 13) ANGMAX maximum angle difference, θf − θt (degrees)
    
        % The voltage angle difference is taken to be unbounded below if ANGMIN ≤ −360 
        % and unbounded above if ANGMAX ≥ 360. If both parameters are zero, 
        % the voltage angle difference is unconstrained.
    
    % 14) PF real power injected at "from" bus end (MW) --> OPF
    % 15) QF reactive power injected at "from" bus end (MVAr) --> OPF
    % 16) PT real power injected at "to" bus end (MW) --> OPF
    % 17) QT reactive power injected at "to" bus end (MVAr) --> OPF
    % 18) MU_SF Kuhn-Tucker multiplier on MVA limit at "from" bus (u/MVA)
    % 19) MU_ST Kuhn-Tucker multiplier on MVA limit at "to" bus (u/MVA) --> OPF
    % 20) MU_ANGMIN Kuhn-Tucker multiplier lower angle difference limit (u/degree) --> OPF
    % 21) MU_ANGMAX Kuhn-Tucker multiplier upper angle difference limit (u/degree) --> OPF
    
    % ---------------------------------------------------------------------
    % GENERATOR DATA
    % ---------------------------------------------------------------------
    
    if shared_power == 0
    
        ngen = height(T_TH) + height(T_SG) + height(T_VSC) + height(T_user);
        gen = zeros(ngen,25);
        
        % 1) GEN_BUS bus number
        gen(:,1) = [T_TH.bus; T_SG.bus; T_VSC.bus; T_user.bus];
        
        % 2) PG real power output (MW)
        gen(:,2) = [T_TH.P; T_SG.P; T_VSC.P; T_user.P]*baseMVA;
        
        % 3) QG reactive power output (MVAr)
        gen(:,3) = [T_TH.Q; T_SG.Q; T_VSC.Q; T_user.Q]*baseMVA;    
        
        % 6) VG voltage magnitude setpoint (p.u.)    
        V = [];
        for idx = 1:height(T_TH)
          busidx = bus(:,1) == T_TH.bus(idx);
          V(end+1) =  bus(busidx,8);
        end  
        for idx = 1:height(T_SG)
          busidx = bus(:,1) == T_SG.bus(idx);
          V(end+1) =  bus(busidx,8);
        end    
        for idx = 1:height(T_VSC)
          busidx = bus(:,1) == T_VSC.bus(idx);
          V(end+1) =  bus(busidx,8);
        end     
        for idx = 1:height(T_user)
          busidx = bus(:,1) == T_user.bus(idx);
          V(end+1) =  bus(busidx,8);
        end
        
        gen(:,6) = V;
        
        % 7) MBASE total MVA base of machine, defaults to baseMVA
        gen(:,7) = [T_TH.Sn; T_SG.Sn; T_VSC.Sn; T_user.Sn];
        
        % 8) GEN_STATUS machine status (>0 = machine in-service)
        gen(:,8) = [T_TH.state; T_SG.state; T_VSC.state; T_user.state];          
    
    elseif shared_power == 1

        % Then assume only one equivalent generator element per bus when
        % there is SG, GFOR and/or GFOL
        % Not all buses need to be equal. Maybe one has three units and
        % another has two...

        % Determine number of generator elements         
        T_SG_VSC = [T_SG(:,["bus","P","Q","Sn","state"]); T_VSC(:,["bus","P","Q","Sn","state"])];
        [~, uniqueIndices, ~] = unique(T_SG_VSC.bus); % Detect if there is more than one generator element
        T_SG_VSC = T_SG_VSC(uniqueIndices,:); %keep first occurrence in each bus
        
        ngen = height(T_TH) + height(T_SG_VSC) + height(T_user);
        gen = zeros(ngen,25);

        % 1) GEN_BUS bus number
        gen(:,1) = [T_TH.bus; T_SG_VSC.bus; T_user.bus];
        
        % 2) PG real power output (MW)
        gen(:,2) = [T_TH.P; T_SG_VSC.P; T_user.P]*baseMVA;
        
        % 3) QG reactive power output (MVAr)
        gen(:,3) = [T_TH.Q; T_SG_VSC.Q; T_user.Q]*baseMVA;    
        
        % 6) VG voltage magnitude setpoint (p.u.)    
        V = [];
        for idx = 1:height(T_TH)
          busidx = bus(:,1) == T_TH.bus(idx);
          V(end+1) =  bus(busidx,8);
        end  
        for idx = 1:height(T_SG_VSC)
          busidx = bus(:,1) == T_SG_VSC.bus(idx);
          V(end+1) =  bus(busidx,8);
        end     
        for idx = 1:height(T_user)
          busidx = bus(:,1) == T_user.bus(idx);
          V(end+1) =  bus(busidx,8);
        end
        
        gen(:,6) = V;
        
        % 7) MBASE total MVA base of machine, defaults to baseMVA
        gen(:,7) = [T_TH.Sn; T_SG_VSC.Sn; T_user.Sn];
        
        % 8) GEN_STATUS machine status (>0 = machine in-service)
        gen(:,8) = [T_TH.state; T_SG_VSC.state; T_user.state];
    
    end

        % 4) QMAX maximum reactive power output (MVAr)
        %gen(:,4) = 9999*ones(ngen,1); %default QT = 9999.0
        gen(:,4) = 1.5*gen(:,7); %default QT = 1.5*Sn
        
        % 5) QMIN minimum reactive power output (MVAr)
        %gen(:,5) = -9999*ones(ngen,1); %default QB = -9999.0
        gen(:,5) = -1.5*gen(:,7); %default QB = -1.5*Sn
        
        % 9) PMAX maximum real power output (MW)
        %gen(:,9) = 9999*ones(ngen,1); %default PT = 9999.0
        gen(:,9) = 1.5*gen(:,7); %default PT = 1.5*Sn
    
        % 10) PMIN minimum real power output (MW)
        %gen(:,10) = -9999*ones(ngen,1); %default PB = -9999.0
        gen(:,10) = -1.5*gen(:,7);  %default PB = -1.5*Sn
    
        % 11) PC1 lower real power output of PQ capability curve (MW)
        % 12) PC2 upper real power output of PQ capability curve (MW)
        % 13) QC1MIN minimum reactive power output at PC1 (MVAr)
        % 14) QC1MAX maximum reactive power output at PC1 (MVAr)
        % 15) QC2MIN minimum reactive power output at PC2 (MVAr)
        % 16) QC2MAX maximum reactive power output at PC2 (MVAr)
        % 17) RAMP_AGC ramp rate for load following/AGC (MW/min)
        % 18) RAMP_10  ramp rate for 10 minute reserves (MW)
        % 19) RAMP_30  ramp rate for 30 minute reserves (MW)
        % 20) RAMP_Q ramp rate for reactive power (2 sec timescale) (MVAr/min)
        % 21) APF area participation factor
        % 22) MU_PMAX  Kuhn-Tucker multiplier on upper Pg limit (u/MW) --> OPF
        % 23) MU_PMIN  Kuhn-Tucker multiplier on lower Pg limit (u/MW) --> OPF
        % 24) MU_QMAX Kuhn-Tucker multiplier on upper Qg limit (u/MVAr) --> OPF
        % 25) MU_QMIN  Kuhn-Tucker multiplier on lower Qg limit (u/MVAr) --> OPF
    
    % ---------------------------------------------------------------------
    % Two-terminal DC transmission line data
    % ---------------------------------------------------------------------
    % ACDC powerflow not implemented yet.
    
    % ---------------------------------------------------------------------
    % Generate mpc struct
    % ---------------------------------------------------------------------
    mpc = struct('baseMVA',  baseMVA, 'bus', bus, 'branch', branch, 'gen', gen);

end
