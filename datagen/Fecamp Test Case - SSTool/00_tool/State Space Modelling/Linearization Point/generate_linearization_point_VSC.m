%% Calculates the linearization point per each MMC
function lp_vsc = generate_linearization_point_VSC(T_VSC, T_global, delta_slk)

lp_vsc = cell(1,height(T_VSC));

    for vsc = 1:1:height(T_VSC)

        Svsc = T_VSC.Sb(vsc);       % SG rated power, SG power base  
        Sb  = T_global.Sb(T_global.Area == T_VSC.Area(vsc)); % System power base

        Rtr = T_VSC.Rtr(vsc);
        Xtr = T_VSC.Xtr(vsc);
        Rc  = T_VSC.Rc(vsc);
        Xc  = T_VSC.Xc(vsc);

        %Data from the power-flow
        delta0   = T_VSC.theta(vsc)*pi/180;
        Vg       = T_VSC.V(vsc)/sqrt(3)/T_VSC.Vbpu_l2g(vsc); 
        Pvsc0    = T_VSC.P(vsc)*(Sb/Svsc);
        Qvsc0    = T_VSC.Q(vsc)*(Sb/Svsc);

        mode = T_VSC.mode{:};

        switch mode

            case 'GFOL_LR'   

                Cac = T_VSC.Cac(vsc);
                Rac = T_VSC.Rac(vsc);
                wb = T_VSC.wb(vsc);

                % Calculation of voltages and currents (REF: NET-POC)
                
                if T_VSC.Cac(vsc)

                    % RLC filter
                    Ig       = conj((Pvsc0+1i*Qvsc0)./(3*Vg));  % Transformer current 
                    phi      = atan2(imag(Ig),real(Ig));        % angle of transformer current
                    U        = Vg + Ig*(Rtr+1i*Xtr);            % Voltage at capacitor bus
                    theta_in = atan2(imag(U),real(U));          % angle between POC and capacitor bus
                    Icap     = U/(Rac-1i/(wb*Cac));             % current through capacitor
                    Ucap     = U - Rac*Icap;
                    theta_ucap = atan2(imag(Ucap),real(Ucap));
                    Is       = Ig + Icap;                       % converter filter current
                    phi_is   = atan2(imag(Is),real(Is));
                    Vc       = U + Is*(Rc+1i*Xc);               % voltage applied by the converter
                    theta_vc = atan2(imag(Vc),real(Vc)); 

                else

                    % RL filter (no capacitor)
                    Is       = conj((Pvsc0+1i*Qvsc0)./(3*Vg));  % converter filter current
                    phi_is      = atan2(imag(Is),real(Is));     % angle of converter filter current
                    U        = Vg + Is*(Rtr+1i*Xtr);            % Voltage at capacitor bus
                    theta_in = atan2(imag(U),real(U));          % angle between POC and capacitor bus                
                    Vc       = U + Is*(Rc+1i*Xc);               % voltage applied by the converter
                    theta_vc = atan2(imag(Vc),real(Vc));

                    % Additional variables
                    Ig = Is;
                    phi = phi_is;
                    Ucap = U;
                    theta_ucap = 0;
                end

            case 'GFOL'   

                Cac = T_VSC.Cac(vsc);
                Rac = T_VSC.Rac(vsc);
                wb = T_VSC.wb(vsc);

                % Calculation of voltages and currents (REF: NET-POC)
                
                if T_VSC.Cac(vsc)

                    % RLC filter
                    Ig       = conj((Pvsc0+1i*Qvsc0)./(3*Vg));  % Transformer current 
                    phi      = atan2(imag(Ig),real(Ig));        % angle of transformer current
                    U        = Vg + Ig*(Rtr+1i*Xtr);            % Voltage at capacitor bus
                    theta_in = atan2(imag(U),real(U));          % angle between POC and capacitor bus
                    Icap     = U/(Rac-1i/(wb*Cac));             % current through capacitor
                    Ucap     = U - Rac*Icap;
                    theta_ucap = atan2(imag(Ucap),real(Ucap));
                    Is       = Ig + Icap;                       % converter filter current
                    phi_is   = atan2(imag(Is),real(Is));
                    Vc       = U + Is*(Rc+1i*Xc);               % voltage applied by the converter
                    theta_vc = atan2(imag(Vc),real(Vc)); 

                else

                    % RL filter (no capacitor)
                    Is       = conj((Pvsc0+1i*Qvsc0)./(3*Vg));  % converter filter current
                    phi_is      = atan2(imag(Is),real(Is));     % angle of converter filter current
                    U        = Vg + Is*(Rtr+1i*Xtr);            % Voltage at capacitor bus
                    theta_in = atan2(imag(U),real(U));          % angle between POC and capacitor bus                
                    Vc       = U + Is*(Rc+1i*Xc);               % voltage applied by the converter
                    theta_vc = atan2(imag(Vc),real(Vc));

                    % Additional variables
                    Ig = Is;
                    phi = phi_is;
                    Ucap = U;
                    theta_ucap = 0;
                end
                
            case 'GFOR'

                Cac = T_VSC.Cac(vsc);
                Rac = T_VSC.Rac(vsc);
                wb = T_VSC.wb(vsc);

                % Calculation of voltages and currents (REF: NET-POC)
                Ig       = conj((Pvsc0+1i*Qvsc0)./(3*Vg));  % Transformer current 
                phi      = atan2(imag(Ig),real(Ig));        % angle of transformer current
                U        = Vg + Ig*(Rtr+1i*Xtr);            % Voltage at capacitor bus
                theta_in = atan2(imag(U),real(U));          % angle between POC and capacitor bus
                Icap     = U/(Rac-1i/(wb*Cac));             % current through capacitor
                Ucap     = U - Rac*Icap;
                theta_ucap = atan2(imag(Ucap),real(Ucap));
                Is       = Ig + Icap;                       % converter filter current
                phi_is   = atan2(imag(Is),real(Is));
                Vc       = U + Is*(Rc+1i*Xc);               % voltage applied by the converter
                theta_vc = atan2(imag(Vc),real(Vc));     
        end

         % Calculate angles
        delta_bus = delta0 - delta_slk;            % NET-POC
        e_theta0  = delta0 + theta_in - delta_slk; % VSC-POC 
        
        % Initial values in qd referenced to GLOBAL REF (add delta_bus: delta0-delta_slk)
        
        % qd GRID voltage (REF:GLOBAL)
        vg_q0 = abs(Vg).*cos(delta_bus)*sqrt(2);
        vg_d0 = -abs(Vg).*sin(delta_bus)*sqrt(2);
        
        % qd VSC-PCC voltage (REF:GLOBAL)
        u_q0 = abs(U).*cos(e_theta0)*sqrt(2);
        u_d0 = -abs(U).*sin(e_theta0)*sqrt(2);
        
        % qd TRAFO current (REF:GLOBAL)
        ig_q0 = abs(Ig).*cos(delta_bus  + phi)*sqrt(2);
        ig_d0 = -abs(Ig).*sin(delta_bus + phi)*sqrt(2);
        
        % VSC current (REF:GLOBAL)
        is_q0 = abs(Is).*cos(delta_bus  + phi_is)*sqrt(2);
        is_d0 = -abs(Is).*sin(delta_bus + phi_is)*sqrt(2);
        
        % qd converter voltage (REF:GLOBAL)
        vc_q0 = abs(Vc).*cos(delta_bus + theta_vc)*sqrt(2); 
        vc_d0 = -abs(Vc).*sin(delta_bus + theta_vc)*sqrt(2); 
        
        % Capacitor voltage GLOBAL
        ucap_q0 = abs(Ucap).*cos(delta_bus + theta_ucap)*sqrt(2);
        ucap_d0 = -abs(Ucap).*sin(delta_bus + theta_ucap)*sqrt(2);
        
        
        % Initial values in qd referenced to VSC REF 
        
        % qd converter voltage (REF:LOCAL)
        [vc_qc0,vc_dc0] = rotation_vect(real(Vc)*sqrt(2), -imag(Vc)*sqrt(2), theta_in);                
        % qd VSC-POC voltage (REF:LOCAL)
        [u_qc0,u_dc0] = rotation_vect(real(U)*sqrt(2), -imag(U)*sqrt(2), theta_in);                
        % qd VSC current (REF:LOCAL)
        [is_qc0,is_dc0] = rotation_vect(real(Is)*sqrt(2), -imag(Is)*sqrt(2), theta_in);
        % qd VSC-POC grid current (REF:LOCAL)
        [ig_qc0,ig_dc0] = rotation_vect(real(Ig)*sqrt(2), -imag(Ig)*sqrt(2), theta_in);
        
        % Store linearization point
        lp.ig_q0 = ig_q0;  
        lp.ig_d0 = ig_d0;
        lp.ig_qc0 = ig_qc0;  
        lp.ig_dc0 = ig_dc0;  
        lp.is_q0 = is_q0; 
        lp.is_d0 = is_d0;
        lp.u_q0  = u_q0;
        lp.u_d0  = u_d0;
        lp.ucap_q0 = ucap_q0; 
        lp.ucap_d0 = ucap_d0;                 
        lp.u_qc0  = u_qc0;
        lp.u_dc0  = u_dc0;
        lp.vc_qc0 = vc_qc0; 
        lp.vc_dc0 = vc_dc0; 
        lp.vg_q0 = vg_q0; 
        lp.vg_d0 = vg_d0; 
        lp.is_qc0 = is_qc0;
        lp.is_dc0 = is_dc0;
        lp.w0_pu = 1;
        lp.w0 = T_VSC.wb(vsc); 
        lp.etheta0 = e_theta0; 
        
        lp_vsc{vsc} = lp;
    end
end