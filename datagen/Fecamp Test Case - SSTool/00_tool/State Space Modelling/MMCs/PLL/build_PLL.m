function PLL = build_PLL(kp_pll, ki_pll, number,nodeAC)    
    % PLL:
    Apll_n = [0];
    Bpll_n = [1];
    Cpll_n = [-ki_pll];
    Dpll_n = [-kp_pll];

    pll_n_x = { join(['VSC',num2str(number),'.PI_pll'])};

    pll_n_u = {join(['VSC',num2str(number),'.vn',num2str(nodeAC),'d_c',num2str(number)])};

    pll_n_y = {join(['VSC',num2str(number),'.omegaPLL'])};

    pll_n = ss(Apll_n,Bpll_n,Cpll_n,Dpll_n,'StateName',pll_n_x,'inputname',pll_n_u,'outputname',pll_n_y);
    
    % e_theta (PLL-Grid):
    Atheta_n = [0];
    Btheta_n = [1 -1];
    Ctheta_n = [1];
    Dtheta_n = [0 0];
    theta_n_x = { join(['VSC',num2str(number),'.I_pll'])};
    theta_n_u = { join(['VSC',num2str(number),'.omegaPLL']);...
                  join(['VSC',num2str(number),'.angle_ref'] ) };
    theta_n_y = { join(['VSC',num2str(number),'.angle'] ) };
    theta_n = ss(Atheta_n,Btheta_n,Ctheta_n,Dtheta_n,'StateName',theta_n_x,'inputname',theta_n_u,'outputname',theta_n_y);
    
    u = [ pll_n_u ; join(['VSC',num2str(number),'.angle_ref'] ) ];
    y = [ theta_n_y ];
    
    %Connect the two PLL sub-modules:
    PLL = connect(pll_n , theta_n, u, y );

end