from stability_analysis.state_space.namedio import NamedIOSystem, _process_signal_list, \
    _process_namedio_keywords, isctime, isdtime, common_timebase
from control.statesp import StateSpace, tf2ss, _convert_to_statespace
from control.nlsys import InterconnectedSystem
from control.bdalg import append, connect
from control import interconnect  
import numpy as np

def append_and_connect(newsys):
    
    llista_sys=newsys.syslist
    llista_u= newsys.input_labels
    llista_y= newsys.output_labels
    llista_x= newsys.state_labels

    llista_sys=[StateSpace(s) for s in llista_sys]

    import time

    start=time.time()

    sys_app=[]
    llista_u_conc=[]
    llista_y_conc=[]
    llista_x_conc=[]

    # i=-1
    for s in llista_sys:
        # i=i+1
        # try:
        sys_app=append(sys_app,s)
        # except:
        #     print(i)
        llista_u_conc.extend(s.input_labels)
        llista_y_conc.extend(s.output_labels)
        llista_x_conc.extend(s.state_labels)

    sys_app.input_my_labels=llista_u_conc

    sys_app.output_my_labels=llista_y_conc

    sys_app.state_my_labels=llista_x_conc

    llista_u_2conn=list(set(llista_u_conc)-set(llista_u))
    
    excluded_u=[]
    for u in llista_u_2conn:
        if any([u in sys.output_labels for sys in llista_sys])==False:
            # print(u)
            excluded_u.append(u)
    
    # sys_inp_indx=[]
    # for u in llista_u_2conn:
    #         sys_inp_indx.extend(np.where(np.array(sys_app.input_my_labels)==u)[0]+1)
            
    # sys_out_indx=[]
    # sys_out_indx_app=[]
    # for y in llista_u_2conn:
    #         n_inp=len(np.where(np.array(sys_app.input_my_labels)==y)[0]+1)
    #         # sys_out_indx.append((np.where(np.array(sys_app.output_my_labels)==y)[0]+1))
    #         for n in range(0,n_inp):
    #             sys_out_indx.extend(np.where(np.array(sys_app.output_my_labels)==y)[0]+1)
    #             sys_out_indx_app.append(np.where(np.array(sys_app.output_my_labels)==y)[0]+1)
                
    #             if len(np.where(np.array(sys_app.output_my_labels)==y)[0])==0:
    #                 print(y)
                    
    sys_inp_indx=[]
    sys_out_indx=[]

    for u in llista_u_2conn:
        if u not in excluded_u:
            sys_inp_indx.extend(np.where(np.array(sys_app.input_my_labels)==u)[0]+1)
            n_inp=len(np.where(np.array(sys_app.input_my_labels)==u)[0]+1)
 
            for n in range(0,n_inp):
                sys_out_indx.extend(np.where(np.array(sys_app.output_my_labels)==u)[0]+1)
                
                # if len(np.where(np.array(sys_app.output_my_labels)==u)[0])==0:
                #     print(u)
                    
   
    
    # for i in range(0,len(llista_sys)):
    #     if y in llista_sys[i].input_labels:
    #         print('inputs ',i)
    #     if y in llista_sys[i].output_labels:    
    #         print('output ',i)

    Q = list(zip(sys_inp_indx, sys_out_indx))

    # uu_idx=[sys_app.input_my_labels.index(u)+1 for u in llista_u]
    # yy_idx=[sys_app.output_my_labels.index(y)+1 for y in llista_y]

    uu_idx_ext=[]
    uu_idx_app=[]
    for u in llista_u:
            uu_idx_ext.extend(np.where(np.array(sys_app.input_my_labels)==u)[0]+1)
            uu_idx_app.append(np.where(np.array(sys_app.input_my_labels)==u)[0]+1)

    
    yy_idx=[]
    yy_idx_app=[]
    for y in llista_y:
            yy_idx.extend(np.where(np.array(sys_app.output_my_labels)==y)[0]+1)
            yy_idx_app.append(np.where(np.array(sys_app.output_my_labels)==y)[0]+1)

    # TODO: Changed connect for interconnect. Recambiado
    sys_conn = connect(sys_app, Q, uu_idx_ext, yy_idx
    )

    # nstates=sys_conn.nstates
    # noutputs=len(uu_idx_app)
    # sys_conn.noutputs=noutputs
    # B=sys_conn.B
    # sys_conn.B=np.zeros([nstates,noutputs])
    
    # D=sys_conn.D
    # sys_conn.D=np.zeros([nstates,noutputs])
    
    nstates=sys_conn.nstates
    ninputs=len(uu_idx_app)
    sys_conn.ninputs=ninputs
    B=sys_conn.B
    sys_conn.B=np.zeros([nstates,ninputs])
    
    D=sys_conn.D
    sys_conn.D=np.zeros([sys_conn.noutputs,ninputs])
    
    idx_1=0
    idx_2=0
    for uu_idx in uu_idx_app:
        sys_conn.B[:,idx_2]=B[:,idx_1:idx_1+len(uu_idx)].sum(axis=1)
        sys_conn.D[:,idx_2]=D[:,idx_1:idx_1+len(uu_idx)].sum(axis=1)
        idx_2=idx_2+1
        idx_1=idx_1+len(uu_idx)
    end=time.time()
    time_conn=end-start
    # print('time_connect',time_conn)

    sys_conn.state_labels=llista_x
    sys_conn.output_labels=llista_y
    sys_conn.input_labels=llista_u

    return sys_conn

def interconnect(
        syslist, connections=None, inplist=None, outlist=None, params=None,
        check_unused=True, add_unused=False, ignore_inputs=None,
        ignore_outputs=None, warn_duplicate=None, **kwargs):
    """Interconnect a set of input/output systems.

    This function creates a new system that is an interconnection of a set of
    input/output systems.  If all of the input systems are linear I/O systems
    (type :class:`~control.LinearIOSystem`) then the resulting system will be
    a linear interconnected I/O system (type :class:`~control.LinearICSystem`)
    with the appropriate inputs, outputs, and states.  Otherwise, an
    interconnected I/O system (type :class:`~control.InterconnectedSystem`)
    will be created.

    Parameters
    ----------
    syslist : list of InputOutputSystems
        The list of input/output systems to be connected

    connections : list of connections, optional
        Description of the internal connections between the subsystems:

            [connection1, connection2, ...]

        Each connection is itself a list that describes an input to one of the
        subsystems.  The entries are of the form:

            [input-spec, output-spec1, output-spec2, ...]

        The input-spec can be in a number of different forms.  The lowest
        level representation is a tuple of the form `(subsys_i, inp_j)` where
        `subsys_i` is the index into `syslist` and `inp_j` is the index into
        the input vector for the subsystem.  If `subsys_i` has a single input,
        then the subsystem index `subsys_i` can be listed as the input-spec.
        If systems and signals are given names, then the form 'sys.sig' or
        ('sys', 'sig') are also recognized.

        Similarly, each output-spec should describe an output signal from one
        of the subsystems.  The lowest level representation is a tuple of the
        form `(subsys_i, out_j, gain)`.  The input will be constructed by
        summing the listed outputs after multiplying by the gain term.  If the
        gain term is omitted, it is assumed to be 1.  If the system has a
        single output, then the subsystem index `subsys_i` can be listed as
        the input-spec.  If systems and signals are given names, then the form
        'sys.sig', ('sys', 'sig') or ('sys', 'sig', gain) are also recognized,
        and the special form '-sys.sig' can be used to specify a signal with
        gain -1.

        If omitted, the `interconnect` function will attempt to create the
        interconnection map by connecting all signals with the same base names
        (ignoring the system name).  Specifically, for each input signal name
        in the list of systems, if that signal name corresponds to the output
        signal in any of the systems, it will be connected to that input (with
        a summation across all signals if the output name occurs in more than
        one system).

        The `connections` keyword can also be set to `False`, which will leave
        the connection map empty and it can be specified instead using the
        low-level :func:`~control.InterconnectedSystem.set_connect_map`
        method.

    inplist : list of input connections, optional
        List of connections for how the inputs for the overall system are
        mapped to the subsystem inputs.  The input specification is similar to
        the form defined in the connection specification, except that
        connections do not specify an input-spec, since these are the system
        inputs. The entries for a connection are thus of the form:

            [input-spec1, input-spec2, ...]

        Each system input is added to the input for the listed subsystem.  If
        the system input connects to only one subsystem input, a single input
        specification can be given (without the inner list).

        If omitted the `input` parameter will be used to identify the list
        of input signals to the overall system.

    outlist : list of output connections, optional
        List of connections for how the outputs from the subsystems are mapped
        to overall system outputs.  The output connection description is the
        same as the form defined in the inplist specification (including the
        optional gain term).  Numbered outputs must be chosen from the list of
        subsystem outputs, but named outputs can also be contained in the list
        of subsystem inputs.

        If an output connection contains more than one signal specification,
        then those signals are added together (multiplying by the any gain
        term) to form the system output.

        If omitted, the output map can be specified using the
        :func:`~control.InterconnectedSystem.set_output_map` method.

    inputs : int, list of str or None, optional
        Description of the system inputs.  This can be given as an integer
        count or as a list of strings that name the individual signals.  If an
        integer count is specified, the names of the signal will be of the
        form `s[i]` (where `s` is one of `u`, `y`, or `x`).  If this parameter
        is not given or given as `None`, the relevant quantity will be
        determined when possible based on other information provided to
        functions using the system.

    outputs : int, list of str or None, optional
        Description of the system outputs.  Same format as `inputs`.

    states : int, list of str, or None, optional
        Description of the system states.  Same format as `inputs`. The
        default is `None`, in which case the states will be given names of the
        form '<subsys_name>.<state_name>', for each subsys in syslist and each
        state_name of each subsys.

    params : dict, optional
        Parameter values for the systems.  Passed to the evaluation functions
        for the system as default values, overriding internal defaults.

    dt : timebase, optional
        The timebase for the system, used to specify whether the system is
        operating in continuous or discrete time.  It can have the following
        values:

        * dt = 0: continuous time system (default)
        * dt > 0: discrete time system with sampling period 'dt'
        * dt = True: discrete time with unspecified sampling period
        * dt = None: no timebase specified

    name : string, optional
        System name (used for specifying signals). If unspecified, a generic
        name <sys[id]> is generated with a unique integer id.

    check_unused : bool, optional
        If True, check for unused sub-system signals.  This check is
        not done if connections is False, and neither input nor output
        mappings are specified.

    add_unused : bool, optional
        If True, subsystem signals that are not connected to other components
        are added as inputs and outputs of the interconnected system.

    ignore_inputs : list of input-spec, optional
        A list of sub-system inputs known not to be connected.  This is
        *only* used in checking for unused signals, and does not
        disable use of the input.

        Besides the usual input-spec forms (see `connections`), an
        input-spec can be just the signal base name, in which case all
        signals from all sub-systems with that base name are
        considered ignored.

    ignore_outputs : list of output-spec, optional
        A list of sub-system outputs known not to be connected.  This
        is *only* used in checking for unused signals, and does not
        disable use of the output.

        Besides the usual output-spec forms (see `connections`), an
        output-spec can be just the signal base name, in which all
        outputs from all sub-systems with that base name are
        considered ignored.

    warn_duplicate : None, True, or False, optional
        Control how warnings are generated if duplicate objects or names are
        detected.  In `None` (default), then warnings are generated for
        systems that have non-generic names.  If `False`, warnings are not
        generated and if `True` then warnings are always generated.


    Examples
    --------
    >>> P = ct.rss(2, 2, 2, strictly_proper=True, name='P')
    >>> C = ct.rss(2, 2, 2, name='C')
    >>> T = ct.interconnect(
    ...     [P, C],
    ...     connections = [
    ...         ['P.u[0]', 'C.y[0]'], ['P.u[1]', 'C.y[1]'],
    ...         ['C.u[0]', '-P.y[0]'], ['C.u[1]', '-P.y[1]']],
    ...     inplist = ['C.u[0]', 'C.u[1]'],
    ...     outlist = ['P.y[0]', 'P.y[1]'],
    ... )

    For a SISO system, this example can be simplified by using the
    :func:`~control.summing_block` function and the ability to automatically
    interconnect signals with the same names:

    >>> P = ct.tf(1, [1, 0], inputs='u', outputs='y')
    >>> C = ct.tf(10, [1, 1], inputs='e', outputs='u')
    >>> sumblk = ct.summing_junction(inputs=['r', '-y'], output='e')
    >>> T = ct.interconnect([P, C, sumblk], inputs='r', outputs='y')

    Notes
    -----
    If a system is duplicated in the list of systems to be connected,
    a warning is generated and a copy of the system is created with the
    name of the new system determined by adding the prefix and suffix
    strings in config.defaults['namedio.linearized_system_name_prefix']
    and config.defaults['namedio.linearized_system_name_suffix'], with the
    default being to add the suffix '$copy'$ to the system name.

    It is possible to replace lists in most of arguments with tuples instead,
    but strictly speaking the only use of tuples should be in the
    specification of an input- or output-signal via the tuple notation
    `(subsys_i, signal_j, gain)` (where `gain` is optional).  If you get an
    unexpected error message about a specification being of the wrong type,
    check your use of tuples.

    In addition to its use for general nonlinear I/O systems, the
    :func:`~control.interconnect` function allows linear systems to be
    interconnected using named signals (compared with the
    :func:`~control.connect` function, which uses signal indices) and to be
    treated as both a :class:`~control.StateSpace` system as well as an
    :class:`~control.InputOutputSystem`.

    The `input` and `output` keywords can be used instead of `inputs` and
    `outputs`, for more natural naming of SISO systems.

    """
    dt = kwargs.pop('dt', None)         # by pass normal 'dt' processing
    name, inputs, outputs, states, _ = _process_namedio_keywords(
        kwargs, end=True)

    if not check_unused and (ignore_inputs or ignore_outputs):
        raise ValueError('check_unused is False, but either '
                         + 'ignore_inputs or ignore_outputs non-empty')

    if connections is False and not inplist and not outlist \
       and not inputs and not outputs:
        # user has disabled auto-connect, and supplied neither input
        # nor output mappings; assume they know what they're doing
        check_unused = False

    # If connections was not specified, set up default connection list
    if connections is None:
        # For each system input, look for outputs with the same name
        connections = []
        for input_sys in syslist:
            for input_name in input_sys.input_labels:
                connect = [input_sys.name + "." + input_name]
                for output_sys in syslist:
                    if input_name in output_sys.output_labels:
                        connect.append(output_sys.name + "." + input_name)
                if len(connect) > 1:
                    connections.append(connect)

        auto_connect = True

    elif connections is False:
        check_unused = False
        # Use an empty connections list
        connections = []

    # If inplist/outlist is not present, try using inputs/outputs instead
    if inplist is None:
        inplist = list(inputs or [])
    if outlist is None:
        outlist = list(outputs or [])

    # Process input list
    if not isinstance(inplist, (list, tuple)):
        inplist = [inplist]
    new_inplist = []
    for signal in inplist:
        # Create an empty connection and append to inplist
        connection = []

        # Check for signal names without a system name
        if isinstance(signal, str) and len(signal.split('.')) == 1:
            # Get the signal name
            signal_name = signal[1:] if signal[0] == '-' else signal
            sign = '-' if signal[0] == '-' else ""

            # Look for the signal name as a system input
            for sys in syslist:
                if signal_name in sys.input_labels:
                    connection.append(sign + sys.name + "." + signal_name)

            # Make sure we found the name
            if len(connection) == 0:
                raise ValueError("could not find signal %s" % signal_name)
            else:
                new_inplist.append(connection)
        else:
            new_inplist.append(signal)
    inplist = new_inplist

    # Process output list
    if not isinstance(outlist, (list, tuple)):
        outlist = [outlist]
    new_outlist = []
    for signal in outlist:
        # Create an empty connection and append to inplist
        connection = []

        # Check for signal names without a system name
        if isinstance(signal, str) and len(signal.split('.')) == 1:
            # Get the signal name
            signal_name = signal[1:] if signal[0] == '-' else signal
            sign = '-' if signal[0] == '-' else ""

            # Look for the signal name as a system output
            for sys in syslist:
                if signal_name in sys.output_index.keys():
                    connection.append(sign + sys.name + "." + signal_name)

            # Make sure we found the name
            if len(connection) == 0:
                raise ValueError("could not find signal %s" % signal_name)
            else:
                new_outlist.append(connection)
        else:
            new_outlist.append(signal)
    outlist = new_outlist

    newsys = InterconnectedSystem(
        syslist, connections=connections, inplist=inplist,
        outlist=outlist, inputs=inputs, outputs=outputs, states=states,
        params=params, dt=dt, name=name, warn_duplicate=warn_duplicate)

    # See if we should add any signals
    if add_unused:
        # Get all unused signals
        dropped_inputs, dropped_outputs = newsys.check_unused_signals(
            ignore_inputs, ignore_outputs, warning=False)

        # Add on any unused signals that we aren't ignoring
        for isys, isig in dropped_inputs:
            inplist.append((isys, isig))
            inputs.append(newsys.syslist[isys].input_labels[isig])
        for osys, osig in dropped_outputs:
            outlist.append((osys, osig))
            outputs.append(newsys.syslist[osys].output_labels[osig])

        # Rebuild the system with new inputs/outputs
        newsys = InterconnectedSystem(
            syslist, connections=connections, inplist=inplist,
            outlist=outlist, inputs=inputs, outputs=outputs, states=states,
            params=params, dt=dt, name=name, warn_duplicate=warn_duplicate)

    # check for implicitly dropped signals
    if check_unused:
        newsys.check_unused_signals(ignore_inputs, ignore_outputs)

    if all([isinstance(sys, StateSpace) for sys in newsys.syslist]):
        newsys=append_and_connect(newsys)

    # # If all subsystems are linear systems, maintain linear structure
    # if all([isinstance(sys, LinearIOSystem) for sys in newsys.syslist]):
    #     return LinearICSystem(newsys, None)

    return newsys