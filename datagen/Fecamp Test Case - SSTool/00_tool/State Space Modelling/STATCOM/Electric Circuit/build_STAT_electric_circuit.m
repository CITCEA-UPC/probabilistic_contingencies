function STAT_electric_circuit = build_STAT_electric_circuit(Req, Leq,number,nodeAC,f)
    w_n=2*pi*f;

   % MMC electric squeme:
    A=[-Req/Leq    -w_n       ;
        w_n         -Req/Leq ];

    B=[1/Leq      0            -1/Leq     0    ;
       0         1/Leq            0     -1/Leq ];

    C=[1 0;
       0 1];
    
    D=[0 0 0 0;
       0 0 0 0];
       
    x={ join(['STAT',num2str(number),'.idiffq'])  ; ...
        join(['STAT',num2str(number),'.idiffd'])  };

    u={ join(['STAT',num2str(number),'.vdiff_q'])  ; ...
        join(['STAT',num2str(number),'.vdiff_d'])  ; ... 
        join(['NET','.vn',num2str(nodeAC),'q'])   ; ...
        join(['NET','.vn',num2str(nodeAC),'d'])   };


    y={ join(['STAT',num2str(number),'.idiffq'])  ;...
        join(['STAT',num2str(number),'.idiffd'])  };
    
    STAT_electric_circuit = ss(A,B,C,D,'StateName',x,'inputname',u,'outputname',y);
end