function com_delay = build_com_delay_2order(x,u,y,t)
    
    % A = [0 1 ; -12/t^2 -6/t^2];
    % B = [0;1];
    % C = [1 -6/t];
    % D = [1];

    a = [1 -6/t 12/t^2];
    b = [1 6/t 12/t^2];

    [A,B,C,D] = tf2ss(a,b);

    com_delay = ss(A,B,C,D,'StateName',x,'inputname',u,'outputname',y);
end