function energy_control = build_energy_control(kp, ki, number)
    A = [0];
    B = [1 -1];
    C = [ki];
    D = [kp -kp];

    x = { join(['VSC',num2str(number),'.PI_Et'])};

    u = {join(['VSC',num2str(number),'.Et_ref'])  ; ... 
         join(['VSC',num2str(number),'.Et'])     };

    y = {join(['VSC',num2str(number),'.isum0_ref'])};

    energy_control = ss(A,B,C,D,'StateName',x,'InputName',u,'OutputName',y);
end