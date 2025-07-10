function v_control = build_V_control(kfeed, ki, number, nodeAC)

% set external in/out
    in = {join(['STAT',num2str(number),'.V_ref'])                       ; ...
          join(['STAT',num2str(number),'.vn',num2str(nodeAC),'_filt'])} ; 

    out = join(['STAT',num2str(number),'.idiffd_ref']);


% PI state-space
    A = [0];
    B = [1];
    C = [ki];
    D = [0];
    
    x_PI = join(['STAT',num2str(number),'xPI_V']);
    u_PI = join(['STAT',num2str(number),'sum_V']);
    y_PI = join(['STAT',num2str(number),'.idiffd_ref']);
    ss_PI = ss(A,B,C,D,'StateName',x_PI,'InputName',u_PI,'OutputName',y_PI);

% Feedback gain state-space
   y_FEED = join(['STAT',num2str(number),'.idiffd_refK']);
   ss_FEED = SS_GAIN(out, y_FEED, kfeed); 

% Sum/Error state-space
    A     = [0];
    B     = [0 0 0];
    C     = [0];
    D     = [1 -1 -1];
    
    x_error = {''}; 
    u_error = [in(:)' {y_FEED}];
    y_error = u_PI;
    ss_ERROR = ss(A,B,C,D,'StateName',x_error,'inputname',u_error,'outputname',y_error);

% Generate V_control state-space
    v_control = connect(ss_PI, ss_FEED, ss_ERROR, in, out);
end