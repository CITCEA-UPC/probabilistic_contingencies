function measurement_delay = build_measurement_delay(x,u,y,tau)
    A= [-1/tau];
    B = [1/tau];
    C = 1;
    D = [0]; 
    measurement_delay = ss(A,B,C,D,'StateName',x,'inputname',u,'outputname',y);
end