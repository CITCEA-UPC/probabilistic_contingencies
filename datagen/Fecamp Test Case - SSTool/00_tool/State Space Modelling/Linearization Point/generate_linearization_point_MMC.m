%% Calculates the linearization point per each MMC
function lp_mmc = generate_linearization_point_MMC(T_MMC,results)

lp_mmc = cell(1,height(T_MMC));

    for mmc = 1:1:height(T_MMC)
        %Data from the MMC:
        nodeAC = T_MMC.NodeAC(mmc);

        Rc = T_MMC.Rc(mmc);
        Lc = T_MMC.Lc(mmc);
        Ra = T_MMC.Ra(mmc);
        La = T_MMC.La(mmc);
        Req = Rc + Ra/2;
        Leq = Lc + La/2;
        w = 2*pi*T_MMC.f(mmc);

        % Coming from the powerflow:
        V       = results.global.Vm(nodeAC)*sqrt(2)/sqrt(3); 
        theta   = results.global.theta(nodeAC)*pi/180; %In radians
        if nodeAC == results.b2b.bus1(mmc)
            P = results.b2b.P1(mmc);
            Q = results.b2b.Q1(mmc);
            Vdc   = results.b2b.Vdc1(mmc);
            Isum  = results.b2b.Idc(mmc)/3;
        else
            P = results.b2b.P2(mmc);
            Q = results.b2b.Q2(mmc);
            Vdc   = results.b2b.Vdc2(mmc);
            Isum  = results.b2b.Idc(mmc)/3;
        end


        %Liniearization point calculation:
        %AC side:
        %AC voltage MMC reference:
        V_q_c = V;
        V_d_c = 0;
        
        %AC voltage NET reference:
        Rotation = [cos(theta) sin(theta); -sin(theta) cos(theta)];
        V_0 = Rotation*[V_q_c ; V_d_c];
        V_q_0 = V_0(1);
        V_d_0 = V_0(2);
        
        %AC current MMC reference:
        is_q_c = (2*P)/(3*V_q_c);
        is_d_c = (2*Q)/(3*V_q_c);
        
        %AC current NET reference:
        is_0 = Rotation*[is_q_c ; is_d_c];
        is_q_0 = is_0(1);
        is_d_0 = is_0(2);
        
        %Vdiff voltage MMC reference:
        Vdiff_q_c = V_q_c + Req*is_q_c + w*Leq*is_d_c;
        Vdiff_d_c = V_d_c + Req*is_d_c - w*Leq*is_q_c;

        %Vdiff voltage NET reference:
        Vdiff_q_0 = V_q_0 + Req*is_q_0 + w*Leq*is_d_0 ;
        Vdiff_d_0 = V_d_0 + Req*is_d_0 - w*Leq*is_q_0;
        
        %DC side:        
        %Vsum:
        Vsum = Vdc - 2*Ra*Isum - 2*La*Isum;
        
        %Generate output:
        lp.vnq0 = V_q_0;
        lp.vnd0 = V_d_0;
        lp.vnq0_c = V_q_c;
        lp.vnd0_c = V_d_c;
        lp.idiffq0 = is_q_0;
        lp.idiffd0 = is_d_0;
        lp.idiffq0_c = is_q_c;
        lp.idiffd0_c = is_d_c;
        lp.vdiffq0 = Vdiff_q_0;
        lp.vdiffd0 = Vdiff_d_0;
        lp.vdiffq0_c = Vdiff_q_c;
        lp.vdiffd0_c = Vdiff_d_c;
        lp.isum0 = Isum;
        lp.vsum0 = Vsum;
        lp.vDC0 = Vdc;
        lp.etheta0 = theta;

        lp_mmc{mmc} = lp;
    end
end