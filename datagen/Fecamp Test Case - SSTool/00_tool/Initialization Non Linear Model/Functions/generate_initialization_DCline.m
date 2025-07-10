function Ini_DC_line = generate_initialization_DCline(results,T_DC_NET,n_line)
    node1 = T_DC_NET(T_DC_NET.Number==n_line,:).NodeA;
    node2 = T_DC_NET(T_DC_NET.Number==n_line,:).NodeB;
    
    Va1 = results.Vdc(node1);
    Vb1 = results.Vdc(node1);
    Vc1 = results.Vdc(node1);

    Va2 = results.Vdc(node2);
    Vb2 = results.Vdc(node2);
    Vc2 = results.Vdc(node2);
    
    Ra = T_DC_NET(T_DC_NET.Number==n_line,:).Ra;
    Rb = T_DC_NET(T_DC_NET.Number==n_line,:).Rb;
    Rc = T_DC_NET(T_DC_NET.Number==n_line,:).Rc;

    La = T_DC_NET(T_DC_NET.Number==n_line,:).La;
    Lb = T_DC_NET(T_DC_NET.Number==n_line,:).Lb;
    Lc = T_DC_NET(T_DC_NET.Number==n_line,:).Lc;

    Za = Ra;
    Zb = Rb;
    Zc = Rc;
   
    Ia = (Va1-Va2)/Za;
    Ib = (Vb1-Vb2)/Zb;
    Ic = (Vc1-Vc2)/Zc;
    
    Ini_DC_line.Ia = abs(Ia);
    Ini_DC_line.Ib = abs(Ib);
    Ini_DC_line.Ic = abs(Ic);

end