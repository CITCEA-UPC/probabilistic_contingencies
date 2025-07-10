function results = matpower2table(bus_pf, gen_pf)

    setup_globals; % Import global variables names

    baseMVA = T_global.Sb_MVA(1); %System power base in power-flow

        % results: struct with fields 'bus', 'load', 'th', 'sg', 'vsc', 'user'
        
        % bus
        results.bus = T_PF;
        results.bus.Vm = bus_pf(:,8);
        results.bus.theta = bus_pf(:,9);
        type = cell(height(T_PF),1);
        for idx = 1:height(T_PF)
            if bus_pf(idx,2) == 1
                type{idx,1} = "PQ";
            elseif bus_pf(idx,2) == 2
                type{idx,1} = "PV";
            elseif bus_pf(idx,2) == 3
                type{idx,1} = "slack";
            elseif bus_pf(idx,2) == 4
                type{idx,1} = "isolated";
            end      
        end
        results.bus(:,"type") = cell2table(type);
        results.bus = [results.bus T_nodes(ismember(T_nodes.Node,bus_pf(:,1)),2:end)];
        
        % load
        results.load = T_load(:,["number","bus","P","Q"]);

        % if any(bus_pf(:,4)<0)
        %     ME = MException('There is a load with Q<0. Capacitive loads are not implemented yet');
        %     throw(ME)         
        % end
        
        for idx = 1:height(T_load)
            busNum = T_load{idx,"bus"};
            row = bus_pf(ismember(bus_pf(:,1),busNum, 'rows'),:);
            results.load{idx,"P"} = row(3)/baseMVA;
            results.load{idx,"Q"} = row(4)/baseMVA;
        end
        
        % TH
        results.th = T_TH(:,["number","bus","P","Q"]);
        for idx = 1:height(T_TH)
            busNum = T_TH.bus(idx);
            results.th.P(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),2)/baseMVA;
            results.th.Q(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),3)/baseMVA;
        end
        
        % SG
        results.sg = T_SG(:,["number","bus","P","Q"]);
        for idx = 1:height(T_SG)
            busNum = T_SG.bus(idx);
            results.sg.P(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),2)/baseMVA;
            results.sg.Q(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),3)/baseMVA;
        end
        
        % VSC
        results.vsc = T_VSC(:,["number","bus","P","Q"]);
        for idx = 1:height(T_VSC)
            busNum = T_VSC.bus(idx);
            results.vsc.P(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),2)/baseMVA;
            results.vsc.Q(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),3)/baseMVA;
        end
        
        % USER
        results.user = T_user(:,["number","bus","P","Q"]);
        for idx = 1:height(T_user)
            busNum = T_user.bus(idx);
            results.vsc.P(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),2)/baseMVA;
            results.vsc.Q(idx) = gen_pf(find(gen_pf(:,1) == busNum,1),3)/baseMVA;
        end

end

