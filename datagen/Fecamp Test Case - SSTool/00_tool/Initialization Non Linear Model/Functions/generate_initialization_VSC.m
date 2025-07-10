function init_VSC = generate_initialization_VSC(T_VSC,T_global)
    
    init_VSC = cell(1,height(T_VSC));

    for vsc = 1:1:height(T_VSC)

        % Base powers
        Svsc = T_VSC.Sb(vsc);       % SG rated power, SG power base  
        Sb  = T_global.Sb(T_global.Area == T_VSC.Area(vsc)); % System power base

        % Rl filter and trafo
        Rtr = T_VSC.Rtr(vsc);
        Xtr = T_VSC.Xtr(vsc);
        Rc  = T_VSC.Rc(vsc);
        Xc  = T_VSC.Xc(vsc);

        %Data from the power-flow
        delta0   = T_VSC.theta(vsc)*pi/180;
        Vg       = (T_VSC.V(vsc)/sqrt(3))/T_VSC.Vbpu_l2g(vsc); % PCC line-neutral voltage RMS 
        Pvsc0    = T_VSC.P(vsc)*(Sb/Svsc);
        Qvsc0    = T_VSC.Q(vsc)*(Sb/Svsc);

        mode = T_VSC.mode{vsc};

        switch mode

            case 'GFOL'   

                Rac = T_VSC.Rac(vsc);
                Cac = T_VSC.Cac(vsc);
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

%                 % Calculation of voltages and currents (REF: NET-POC)
%                 Is       = conj((Pvsc0+1i*Qvsc0)./(3*Vg));  % converter filter current 
%                 phi_is   = atan2(imag(Is),real(Is));
%                 U        = Vg + Is*(Rtr+1i*Xtr);            % Voltage at capacitor bus    
%                 theta_in = atan2(imag(U),real(U));          % angle between POC and capacitor bus
%                 Vc       = U + Is*(Rc+1i*Xc);               % voltage applied by the converter
%                 theta_vc = atan2(imag(Vc),real(Vc)); 


                % Initial values in qd referenced to GLOBAL REF
        
                delta_bus = delta0; % NET-POC
        
                % qd GRID voltage (REF:GLOBAL)
                vg_q0 = abs(Vg).*cos(delta_bus)*sqrt(2);
                vg_d0 = -abs(Vg).*sin(delta_bus)*sqrt(2);
                
                % qd VSC-PCC voltage (REF:GLOBAL)
                u_q0 = abs(U).*cos(delta_bus  + theta_in)*sqrt(2);
                u_d0 = -abs(U).*sin(delta_bus + theta_in)*sqrt(2);      

                % qd TRAFO current (REF:GLOBAL)
                ig_q0 = abs(Ig).*cos(delta_bus  + phi)*sqrt(2);
                ig_d0 = -abs(Ig).*sin(delta_bus + phi)*sqrt(2);
                
                % VSC current (REF:GLOBAL)
                is_q0 = abs(Is).*cos(delta_bus  + phi_is)*sqrt(2);
                is_d0 = -abs(Is).*sin(delta_bus + phi_is)*sqrt(2);
                
                % qd converter voltage (REF:GLOBAL)
                vc_q0 = abs(Vc).*cos(delta_bus  + theta_vc)*sqrt(2); 
                vc_d0 = -abs(Vc).*sin(delta_bus + theta_vc)*sqrt(2); 

                % Capacitor voltage (REF:GLOBAL)
                ucap_q0 = abs(Ucap).*cos(delta_bus + theta_ucap)*sqrt(2);
                ucap_d0 = -abs(Ucap).*sin(delta_bus + theta_ucap)*sqrt(2);
                        
        
                % Initial values in qd referenced to VSC REF 
        
                % qd converter voltage (REF:LOCAL)
                [vc_qc0,vc_dc0] = rotation_vect(real(Vc)*sqrt(2), -imag(Vc)*sqrt(2), theta_in);                
                % qd VSC-POC voltage (REF:LOCAL)
                [u_qc0,u_dc0]   = rotation_vect(real(U)*sqrt(2),  -imag(U)*sqrt(2), theta_in);                
                % qd VSC-POC current (REF:LOCAL)
                [is_qc0,is_dc0] = rotation_vect(real(Is)*sqrt(2),-imag(Is)*sqrt(2), theta_in);
                % qd NET-POC current (REF:LOCAL)
                [ig_qc0,ig_dc0] = rotation_vect(real(Ig)*sqrt(2),-imag(Ig)*sqrt(2), theta_in);
      
                % PLL 
                initVSC.thetaPLL_init = delta0 + theta_in -pi/2; % the -pi/2 is necessary due to the PLL being locked in the peak value of the waveform and the theta must be the one from the power flow... same signal!
        
                % Udiff converter voltage in abc, REF:GLOBAL
        
                Udiff_mag = sqrt(vc_q0^2+vc_d0^2);
                initVSC.Udiff_mag   = Udiff_mag*T_VSC.Vbpu_l2g(vsc);
                initVSC.angle_vdiff = delta_bus  + theta_vc;

                initVSC.vdiffd = vc_dc0;
                initVSC.vdiffq = vc_qc0;
        
                % Is (=Idiff) converter current in abc, REF:GLOBAL
        
                Is_mag = sqrt(is_q0^2+is_d0^2)*T_VSC.Ibpu_l2g(vsc);
        
                Isa_VSC = Is_mag*sin(delta_bus + phi_is);
                Isb_VSC = Is_mag*sin(delta_bus + phi_is -2*pi/3);
                Isc_VSC = Is_mag*sin(delta_bus + phi_is +2*pi/3);
        
                initVSC.Isa = Isa_VSC;
                initVSC.Isb = Isb_VSC;
                initVSC.Isc = Isc_VSC;  
        
                % Is (=Idiff) converter current in qd, REF: LOCAL
        
                initVSC.idiffd = is_dc0;
                initVSC.idiffq = is_qc0;     
        
                % Ig transformer current in abc, REF:GLOBAL
        
%               Ig_mag = sqrt(is_q0^2+is_d0^2)*T_VSC.Ibpu_l2g(vsc);
%         
%               Iga = Ig_mag*sin(delta_bus + phi_is);
%               Igb = Ig_mag*sin(delta_bus + phi_is -2*pi/3);
%               Igc = Ig_mag*sin(delta_bus + phi_is +2*pi/3);
%         
%               initVSC.Iga = Iga;
%               initVSC.Igb = Igb;
%               initVSC.Igc = Igc;  
        
                Ig_mag = sqrt(ig_q0^2+ig_d0^2)*T_VSC.Ibpu_l2g(vsc);
        
                Iga = Ig_mag*sin(delta_bus + phi);
                Igb = Ig_mag*sin(delta_bus + phi -2*pi/3);
                Igc = Ig_mag*sin(delta_bus + phi +2*pi/3);
        
                initVSC.Iga = Iga;
                initVSC.Igb = Igb;
                initVSC.Igc = Igc;  

                % U converter-POC voltage in abc, REF:LOCAL
        
                initVSC.ud = u_dc0;
                initVSC.uq = u_qc0;

                % Ig NET-POC current, REF:LOCAL        
                initVSC.igd = ig_dc0;
                initVSC.igq = ig_qc0;
                
                % Differential current loops 
                Udiff_q = vc_qc0;
                Udiff_d = vc_dc0;
        
                initVSC.PI_idiffq =  Udiff_q - initVSC.uq - Xc*initVSC.idiffd;
                initVSC.PI_idiffd =  Udiff_d - initVSC.ud + Xc*initVSC.idiffq;
                initVSC.PI_idiff0 = 0;
        
                %Voltage controller, REF:LOCAL
                initVSC.PI_V = initVSC.idiffd;
                initVSC.ud = u_dc0;
                initVSC.uq = u_qc0;       
        
                % RL filter
                initVSC.Rtr = T_VSC.Rtr(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Ltr = T_VSC.Ltr(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Rc = T_VSC.Rc(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Lc = T_VSC.Lc(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Rac = T_VSC.Rac(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Cac = T_VSC.Cac(vsc)/T_VSC.Zbpu_l2g(vsc); 

                % Capacitor initial voltages, REF:GLOBAL
                Ucap_mag = sqrt(ucap_q0^2+ucap_d0^2)*T_VSC.Vbpu_l2g(vsc);
        
                initVSC.Ucap_a = Ucap_mag*sin(delta_bus + theta_ucap);
                initVSC.Ucap_b = Ucap_mag*sin(delta_bus + theta_ucap -2*pi/3);
                initVSC.Ucap_c = Ucap_mag*sin(delta_bus + theta_ucap +2*pi/3);

                % PQ references
                %Scap = 3*U*conj(Is); %no capacitor
                Scap = 3*U*conj(Ig);
                initVSC.Pref = real(Scap);
                initVSC.Qref = imag(Scap); 
                initVSC.delay = 5e-6;
                

            case 'GFOR'

                Rac = T_VSC.Rac(vsc);
                Cac = T_VSC.Cac(vsc);
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
        
                % Initial values in qd referenced to GLOBAL REF
        
                delta_bus = delta0; % NET-POC
        
                % qd GRID voltage (REF:GLOBAL)
                vg_q0 = abs(Vg).*cos(delta_bus)*sqrt(2);
                vg_d0 = -abs(Vg).*sin(delta_bus)*sqrt(2);
                
                % qd VSC-PCC voltage (REF:GLOBAL)
                u_q0 = abs(U).*cos(delta_bus  + theta_in)*sqrt(2);
                u_d0 = -abs(U).*sin(delta_bus + theta_in)*sqrt(2);
                
                % qd TRAFO current (REF:GLOBAL)
                ig_q0 = abs(Ig).*cos(delta_bus  + phi)*sqrt(2);
                ig_d0 = -abs(Ig).*sin(delta_bus + phi)*sqrt(2);
                
                % VSC current (REF:GLOBAL)
                is_q0 = abs(Is).*cos(delta_bus  + phi_is)*sqrt(2);
                is_d0 = -abs(Is).*sin(delta_bus + phi_is)*sqrt(2);
                
                % qd converter voltage (REF:GLOBAL)
                vc_q0 = abs(Vc).*cos(delta_bus  + theta_vc)*sqrt(2); 
                vc_d0 = -abs(Vc).*sin(delta_bus + theta_vc)*sqrt(2); 
                
                % Capacitor voltage (REF:GLOBAL)
                ucap_q0 = abs(Ucap).*cos(delta_bus + theta_ucap)*sqrt(2);
                ucap_d0 = -abs(Ucap).*sin(delta_bus + theta_ucap)*sqrt(2);
        
        
                % Initial values in qd referenced to VSC REF 
        
                % qd transformer NET-POC voltage (REF:LOCAL)
                [vg_qc0,vg_dc0] = rotation_vect(real(Vg)*sqrt(2), -imag(Vg)*sqrt(2), theta_in);   
                % qd converter voltage (REF:LOCAL)
                [vc_qc0,vc_dc0] = rotation_vect(real(Vc)*sqrt(2), -imag(Vc)*sqrt(2), theta_in);                
                % qd VSC-POC voltage (REF:LOCAL)
                [u_qc0,u_dc0]   = rotation_vect(real(U)*sqrt(2),  -imag(U)*sqrt(2), theta_in);                
                % qd VSC-POC current (REF:LOCAL)
                [is_qc0,is_dc0] = rotation_vect(real(Is)*sqrt(2),-imag(Is)*sqrt(2), theta_in);
                % qd NET-POC current (REF:LOCAL)
                [ig_qc0,ig_dc0] = rotation_vect(real(Ig)*sqrt(2),-imag(Ig)*sqrt(2), theta_in);
        
                % PLL 
                initVSC.thetaPLL_init = delta0 + theta_in -pi/2; % the -pi/2 is necessary due to the PLL being locked in the peak value of the waveform and the theta must be the one from the power flow... same signal!
        
                % Udiff converter voltage in abc, REF:GLOBAL
        
                Udiff_mag = sqrt(vc_q0^2+vc_d0^2);
                initVSC.Udiff_mag   = Udiff_mag*T_VSC.Vbpu_l2g(vsc);
                initVSC.angle_vdiff = delta_bus  + theta_vc;
                
                initVSC.vdiffd = vc_dc0;
                initVSC.vdiffq = vc_qc0;
                
                % Is (=Idiff) converter current in abc, REF:GLOBAL
        
                Is_mag = sqrt(is_q0^2+is_d0^2)*T_VSC.Ibpu_l2g(vsc);
        
                Isa_VSC = Is_mag*sin(delta_bus + phi_is);
                Isb_VSC = Is_mag*sin(delta_bus + phi_is -2*pi/3);
                Isc_VSC = Is_mag*sin(delta_bus + phi_is +2*pi/3);
        
                initVSC.Isa = Isa_VSC;
                initVSC.Isb = Isb_VSC;
                initVSC.Isc = Isc_VSC;  
        
                % Is (=Idiff) converter current in qd, REF: LOCAL
        
                initVSC.idiffd = is_dc0;
                initVSC.idiffq = is_qc0;     
        
                % Ig transformer current in abc, REF:GLOBAL
        
                Ig_mag = sqrt(ig_q0^2+ig_d0^2)*T_VSC.Ibpu_l2g(vsc);
        
                Iga = Ig_mag*sin(delta_bus + phi);
                Igb = Ig_mag*sin(delta_bus + phi -2*pi/3);
                Igc = Ig_mag*sin(delta_bus + phi +2*pi/3);
        
                initVSC.Iga = Iga;
                initVSC.Igb = Igb;
                initVSC.Igc = Igc;  
        
                % U converter-POC voltage in abc, REF:LOCAL
        
                initVSC.ud = u_dc0;
                initVSC.uq = u_qc0;
        
                % Ig NET-POC current, REF:LOCAL
        
                initVSC.igd = ig_dc0;
                initVSC.igq = ig_qc0;
        
                % Differential current loops 
                Udiff_q = vc_qc0;
                Udiff_d = vc_dc0;
        
                initVSC.PI_idiffq =  Udiff_q - initVSC.uq - Xc*initVSC.idiffd;
                initVSC.PI_idiffd =  Udiff_d - initVSC.ud + Xc*initVSC.idiffq;
                initVSC.PI_idiff0 = 0;
        
                %Voltage controller, REF:LOCAL
                initVSC.PI_V = initVSC.idiffd;
                initVSC.ud = u_dc0;
                initVSC.uq = u_qc0;
        
                % Grid-Forming Loops: 
                initVSC.PI_vacq =  initVSC.idiffq - wb*Cac*initVSC.ud - initVSC.igq;
                initVSC.PI_vacd =  initVSC.idiffd + wb*Cac*initVSC.uq - initVSC.igd;
        
                % RL filter
                initVSC.Rtr = T_VSC.Rtr(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Ltr = T_VSC.Ltr(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Rc = T_VSC.Rc(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Lc = T_VSC.Lc(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Rac = T_VSC.Rac(vsc)*T_VSC.Zbpu_l2g(vsc);
                initVSC.Cac = T_VSC.Cac(vsc)/T_VSC.Zbpu_l2g(vsc); 
        
                % Capacitor initial voltages, REF:GLOBAL
                Ucap_mag = sqrt(ucap_q0^2+ucap_d0^2)*T_VSC.Vbpu_l2g(vsc);
        
                initVSC.Ucap_a = Ucap_mag*sin(delta_bus + theta_ucap);
                initVSC.Ucap_b = Ucap_mag*sin(delta_bus + theta_ucap -2*pi/3);
                initVSC.Ucap_c = Ucap_mag*sin(delta_bus + theta_ucap +2*pi/3);
        
                % PQ references
                Scap = 3*U*conj(Ig);
                initVSC.Pref = real(Scap);
                initVSC.Qref = imag(Scap); 
                initVSC.delay = 5e-6;

            case 'STATCOM'

        end     


        init_VSC{vsc} = initVSC;
        
    end
end
