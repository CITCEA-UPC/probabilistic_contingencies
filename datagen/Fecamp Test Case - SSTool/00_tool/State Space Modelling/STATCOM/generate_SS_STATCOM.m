function T_STATCOM  = generate_SS_STATCOM(T_STATCOM, lp_stat, Connectivity_Matrix)

    for stat = 1:1:size(T_STATCOM.bus,1) 
        lp      = lp_stat{stat};
        T_STAT  = T_STATCOM(stat,:);
        STATnum = T_STAT.number;
        bus     = T_STAT.bus;

    %% Outer Loops:
        T_STATCOM.ss_V_control{stat}      = build_V_control(T_STAT.KfeedVac, T_STAT.kiVac, STATnum,bus);

        %Low pass filter for the Vac droop control:
        T_STATCOM.ss_vac_lp_filter{stat}  = build_vac_low_pass_filter_STAT(T_STAT.tVac, lp.vnq0_c, lp.vnd0_c, STATnum, bus);
    
    %% Inner Loops
        T_STATCOM.ss_is_current_control{stat}   = build_STAT_current_control(T_STAT.kpIs, T_STAT.kiIs, T_STAT.Leq ,T_STAT.fn, STATnum,bus);
            
    %% PLL:
        T_STATCOM.ss_PLL{stat}                  = build_STAT_PLL(T_STAT.kpPLL, T_STAT.kiPLL, STATnum, bus);   

    %% STAT electric system:
        T_STATCOM.ss_electric_circuit{stat}     = build_STAT_electric_circuit(T_STAT.Req, T_STAT.Leq, STATnum,bus,T_STAT.fn);

    %% Transformer    
        if isequal(T_STATCOM.trafo{:},'Yes')
            [T_STATCOM.ss_trafo{stat},in_currents]  = build_STAT_trafo(bus,STATnum,Connectivity_Matrix,T_STAT.fn,T_STAT.rm_trafo); 
        end
    %% Rotation matrix for all the input/output signals:

    %From global to local:
        %idiff:
        u = {  join(['STAT',num2str(STATnum),'.idiffq']) ;... 
               join(['STAT',num2str(STATnum),'.idiffd']) ;... 
               join(['STAT',num2str(STATnum),'.angle']) };
        y = {  join(['STAT',num2str(STATnum),'.idiffq_predelay']) ;... 
               join(['STAT',num2str(STATnum),'.idiffd_predelay'])};

        T_STATCOM.global_to_local_idiff{stat}   = build_global_to_local(lp.etheta0, lp.idiffq0, lp.idiffd0 , u , y);
       
        %vn:
        u = { join(['NET','.vn',num2str(bus),'q']) ;... 
              join(['NET','.vn',num2str(bus),'d']) ;...
              join(['STAT',num2str(STATnum),'.angle'] )};
        y = { join(['STAT',num2str(STATnum),'.vq_predelay']) ;... 
              join(['STAT',num2str(STATnum),'.vd_predelay']) };

        T_STATCOM.global_to_local_vn{stat}      = build_global_to_local(lp.etheta0, lp.vnq0, lp.vnd0 , u , y);
        
    %From local to global:
        %vdiff
        u = { join( ['STAT',num2str(STATnum),'.vdiff_q_c',num2str(STATnum)] ); ...
              join( ['STAT',num2str(STATnum),'.vdiff_d_c',num2str(STATnum)] ); ...
              join(['STAT',num2str(STATnum),'.angle'])};
        y = { join( ['STAT',num2str(STATnum),'.vdiff_q'] ) ;...
              join( ['STAT',num2str(STATnum),'.vdiff_d'] )};

        T_STATCOM.local_to_global_vdiff{stat}   = build_local_to_global(lp.etheta0, lp.vdiffq0_c, lp.vdiffd0_c, u , y);

    %% All signal delays:

        %Uq
        delay_x = join(['STAT',num2str(STATnum),'.delay_vq']);
        delay_u = join(['STAT',num2str(STATnum),'.vq_predelay']);
        delay_y = join(['STAT',num2str(STATnum),'.vn',num2str(bus),'q_c',num2str(STATnum)]);
        T_STATCOM.uq_delay{stat}     = build_delay(T_STAT.delay,delay_x,delay_u,delay_y);
        
        %Ud
        delay_x = join(['STAT',num2str(STATnum),'.delay_vd']);
        delay_u = join(['STAT',num2str(STATnum),'.vd_predelay']);
        delay_y = join(['STAT',num2str(STATnum),'.vn',num2str(bus),'d_c',num2str(STATnum)]);
        T_STATCOM.ud_delay{stat}     = build_delay(T_STAT.delay,delay_x,delay_u,delay_y);
        
        %idiffq
        delay_x = join(['STAT',num2str(STATnum),'.delay_idiffq']);
        delay_u = join(['STAT',num2str(STATnum),'.idiffq_predelay']);
        delay_y = join(['STAT',num2str(STATnum),'.idiffq_c',num2str(STATnum)]);
        T_STATCOM.idiffq_delay{stat} = build_delay(T_STAT.delay, delay_x, delay_u, delay_y);
        
        %idiffd
        delay_x = join(['STAT',num2str(STATnum),'.delay_idiffd']);
        delay_u = join(['STAT',num2str(STATnum),'.idiffd_predelay']);
        delay_y = join(['STAT',num2str(STATnum),'.idiffd_c',num2str(STATnum)]);
        T_STATCOM.idiffd_delay{stat} = build_delay(T_STAT.delay, delay_x, delay_u, delay_y);
    
    %% Connect
        if isequal(T_STATCOM.trafo{:},'Yes')
            u = {join(['STAT',num2str(STATnum),'.V_ref'])  ;...
                 join(['STAT',num2str(STATnum),'.idiffq_ref'])  ;...
                 join(['STAT',num2str(STATnum),'.angle_ref'] )                   };
            
            % Add currents to the inputs:
            u = [u;in_currents];
                
            y = {join(['NET','.vn',num2str(bus),'q'])   ;... 
                 join(['NET','.vn',num2str(bus),'d'])  
                 join(['STAT',num2str(STATnum),'.omegaPLL'])};
    
            T_STATCOM.ss{stat} = connect(T_STATCOM.ss_V_control{stat}, T_STATCOM.ss_vac_lp_filter{stat},...
                                         T_STATCOM.ss_is_current_control{stat}, T_STATCOM.ss_PLL{stat}, T_STATCOM.ss_electric_circuit{stat},...
                                         T_STATCOM.ss_trafo{stat}, T_STATCOM.global_to_local_idiff{stat}, T_STATCOM.global_to_local_vn{stat},...
                                         T_STATCOM.local_to_global_vdiff{stat},T_STATCOM.uq_delay{stat}, T_STATCOM.ud_delay{stat},...
                                         T_STATCOM.idiffq_delay{stat}, T_STATCOM.idiffd_delay{stat},u,y);
        else
            u = {join(['NET','.vn',num2str(T_STAT.bus),'q']);... 
                 join(['NET','.vn',num2str(T_STAT.bus),'d']);...
                 join(['STAT',num2str(STATnum),'.V_ref'])         ;...
                 join(['STAT',num2str(STATnum),'.idiffq_ref'])    ;...
                 join(['STAT',num2str(STATnum),'.angle_ref'] ) }  ;
        
            y = {join(['STAT',num2str(T_STAT.number),'.idiffq']);... 
                 join(['STAT',num2str(T_STAT.number),'.idiffd'])
                 join(['STAT',num2str(STATnum),'.omegaPLL'])};
    
            T_STATCOM.ss{stat} = connect(T_STATCOM.ss_V_control{stat}, T_STATCOM.ss_vac_lp_filter{stat},...
                                         T_STATCOM.ss_is_current_control{stat}, T_STATCOM.ss_PLL{stat}, T_STATCOM.ss_electric_circuit{stat},...
                                         T_STATCOM.global_to_local_idiff{stat}, T_STATCOM.global_to_local_vn{stat},...
                                         T_STATCOM.local_to_global_vdiff{stat},T_STATCOM.uq_delay{stat}, T_STATCOM.ud_delay{stat},...
                                         T_STATCOM.idiffq_delay{stat}, T_STATCOM.idiffd_delay{stat},u,y);
    
    
        end
    end
end