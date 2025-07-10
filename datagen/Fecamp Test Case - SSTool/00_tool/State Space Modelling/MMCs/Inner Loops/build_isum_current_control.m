function isum_current_control = build_isum_current_control(kp, ki, number)
    % Additive current control (only 0 sequence)
    A = [0];
    B = [1 -1 0];
    C = [-ki;
          0];
    D = [-kp kp 1;
          0 -3 0];
            
    x = { join(['VSC',num2str(number),'.PI_isum0']) };

    u = { join(['VSC',num2str(number),'.isum0_ref'])      ;... 
          join(['VSC',num2str(number),'.isum0_delay'])    ;... 
          join(['VSC',num2str(number),'.vDC_delay'])}     ;

    y = { join(['VSC',num2str(number),'.vsum0']) ;...
          join(['VSC',num2str(number),'.iDC'])}  ;
    
    isum_current_control = ss(A,B,C,D,'StateName',x,'inputname',u,'outputname',y);
end