% Inputs:  ·T_NET: Table with the AC grid data
%          ·T_MMC_Pac_GFll: Table with the MMC data controlling the AC
%                           power
%          ·T_MMC_Vdc_GFll: Table with the MMC data controlling the DC
%                           voltage
%          ·T_SG:  Table with the SG data
% Outputs: ·Connectivity_Matrix: Matrix of the AC system, which bus_from is
%           connected to which bus_to
%          ·T_nodes: Table of nodes specifying which element/s is/are connected
%           in this node
function [DC_Connectivity_Matrix, T_DC_nodes] = generate_DC_connectivity_matrix(T_DC_NET, T_MMC_GFll_Vdc,T_MMC_GFll_Pac)
    % Connectivity Matrix generation:
    n_nodes = max([max(T_DC_NET.bus_from),max(T_DC_NET.bus_to)]);
    DC_Connectivity_Matrix = zeros(n_nodes);
    for i=1:1:size(T_DC_NET.bus_from,1)
        DC_Connectivity_Matrix(T_DC_NET.bus_from(i),T_DC_NET.bus_to(i))=1;
    end
    DC_Connectivity_Matrix = DC_Connectivity_Matrix + DC_Connectivity_Matrix';
    
    % Nodes specification:
    nsb = sum(ismember(T_MMC_GFll_Vdc.NodeDC,T_MMC_GFll_Pac.NodeDC)); %Number of elements connected to the same DC bus             
    tn = max(max(T_DC_NET.bus_from,T_DC_NET.bus_to));                     %Total node number
    sz = [tn nsb+2];                                                  %Table size
    varNames = strings(nsb+2,1);
    varNames(1) = "Node";
    for i=1:1:(nsb+1)
        varNames(i+1) = strjoin(["Element",num2str(i)],'_');
    end
    varTypes = strings(nsb+2,1);
    varTypes(1) = "double";
    for i=1:1:(nsb+1)
        varTypes(i+1) = "string";
    end
    T_DC_nodes = table('Size',sz,'VariableTypes',varTypes,'VariableNames',varNames);
    %Assign values to the T_nodes table
    T_DC_nodes.Node(1:end) = 1:1:size(T_DC_nodes.Node,1);
    for mmc=1:1:size(T_MMC_GFll_Vdc.NodeDC,1)
        for i =2:1:nsb+2
            if ismissing(T_DC_nodes(T_MMC_GFll_Vdc.NodeDC(mmc),i))
                T_DC_nodes{T_MMC_GFll_Vdc.NodeDC(mmc),i}="MMC_Vdc_GFll";
                break
            end
        end
    end
    for mmc=1:1:size(T_MMC_GFll_Pac.NodeDC,1)
        for i =2:1:nsb+2
            if ismissing(T_DC_nodes(T_MMC_GFll_Pac.NodeDC(mmc),i))
                T_DC_nodes{T_MMC_GFll_Pac.NodeDC(mmc),i}="MMC_Pac_GFll";
                break
            end
        end
    end
end