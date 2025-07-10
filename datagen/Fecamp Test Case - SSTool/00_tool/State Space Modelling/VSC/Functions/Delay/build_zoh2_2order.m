function zoh = build_zoh2_2order(t,x,u,y)

    A = [0 1 ; -12/t^2 -6/t^2];
    B = [0;1];
    C = [1 -6/t];
    D = [1];

    a = [12/t];
    b = [t 6 12/t];

    [A,B,C,D] = tf2ss(a,b);
    
    zoh = ss(A,B,C,D,'StateName',x,'inputname',u,'outputname',y);
end