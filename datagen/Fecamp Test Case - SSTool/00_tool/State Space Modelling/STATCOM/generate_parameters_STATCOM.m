function [T_STATCOM] = generate_parameters_STATCOM(T_STATCOM)

    for stat = 1:1:height(T_STATCOM)
        % Transformer
        T_STATCOM.rm_trafo(stat) = T_STATCOM.Sb_trafo(stat)/T_STATCOM.Wo(stat);
        %T_STATCOM.xm_trafo(stat) = inf; no given data
        T_STATCOM.x_trafo(stat) = T_STATCOM.x_trafo(stat);
        T_STATCOM.r_trafo(stat) = T_STATCOM.Wcc(stat)/T_STATCOM.Sb_trafo(stat);
        
        % Machine base
        Vb = sqrt(2)*T_STATCOM.Vac_ll_rms(stat)*1e3/sqrt(3);
        Sb = T_STATCOM.Sn(stat)*1e6;
        wb = 2*pi*T_STATCOM.fn(stat);
        Zb = Vb^2/Sb;
        Lb = Zb/wb;
    
        % Phase RL
        T_STATCOM.Lc(stat) = T_STATCOM.Lc_mH(stat)*1e-3/Lb;
        T_STATCOM.Rc(stat) = T_STATCOM.Lc(stat)/0.1;  % X/R = 0.1
        
        T_STATCOM.Req(stat) = T_STATCOM.Rc(stat); + T_STATCOM.r_trafo(stat);
        T_STATCOM.Leq(stat) = T_STATCOM.Lc(stat); + T_STATCOM.x_trafo(stat)/wb;

        T_STATCOM.Req(stat) = 0.000977651107115;
        T_STATCOM.Leq(stat) = 0.0001810869036611294;
    end

end

