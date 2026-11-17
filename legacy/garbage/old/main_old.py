import GridCalEngine.api as gce
import numpy as np
# Grid
grid = gce.MultiCircuit()
# Buses
b1 = gce.Bus(name="Bus 1", active=True, is_slack=True, Vnom=139.92, vmin=0.94, vmax=1.06, xpos=-1818.3038229376257,
             ypos=-289.5674044265594, height=60.0, width=118.38229376257573, )
grid.add_bus(b1)

b2 = gce.Bus(name="Bus 2", active=True, is_slack=False, Vnom=137.94, vmin=0.94, vmax=1.06, xpos=-1565.0845070422536,
             ypos=-388.4325955734407, height=60.0, width=94.05633802816897)
grid.add_bus(b2)

b3 = gce.Bus(name="Bus 3", active=True, is_slack=False, Vnom=133.32, vmin=0.94, vmax=1.06, xpos=-1348.0, ypos=-399.0,
             height=60.0, width=123.24748490945672)
grid.add_bus(b3)

b4 = gce.Bus(name="Bus 4", active=True, is_slack=False, Vnom=134.46, vmin=0.94, vmax=1.06, xpos=-1446.0, ypos=-756.0,
             height=60.0, width=132.97786720321938)
grid.add_bus(b4)

b5 = gce.Bus(name="Bus 5", active=True, is_slack=False,
             Vnom=134.67, vmin=0.94, vmax=1.06, xpos=-1789.5452716297787, ypos=-535.2977867203219, height=60.0,
             width=123.24748490945672)
grid.add_bus(b5)

b6 = gce.Bus(name="Bus 6", active=True, is_slack=False, Vnom=35.31, vmin=0.94, vmax=1.06, xpos=-2463.0734678396243,
             ypos=-462.3300473926501, height=60.0, width=114.42434664769326)
grid.add_bus(b6)

b7 = gce.Bus(name="Bus 7", active=True, is_slack=False, Vnom=1.06, vmin=0.94, vmax=1.06, xpos=-1488.0, ypos=-1031.0,
             height=60.0, width=122.89035612622297)
grid.add_bus(b7)

b8 = gce.Bus(name="Bus 8", active=True, is_slack=False, Vnom=11.99, vmin=0.94, vmax=1.06, xpos=-1374.8015436678645,
             ypos=-1303.5756533523074, height=60.0, width=114.42434664769303)
grid.add_bus(b8)

b9 = gce.Bus(name="Bus 9", active=True, is_slack=False, Vnom=34.86, vmin=0.94, vmax=1.06, xpos=-1753.0942992550429,
             ypos=-988.822375083283, height=61.20942992550431, width=109.58662694567602)
grid.add_bus(b9)

b10 = gce.Bus(name="Bus 10", active=True, is_slack=False, Vnom=34.69, vmin=0.94, vmax=1.06, xpos=-2022.6519114688128,
              ypos=-932.5674044265594, height=60.0, width=120.814889336016)
grid.add_bus(b10)

b11 = gce.Bus(name="Bus 11", active=True, is_slack=False, Vnom=34.88, vmin=0.94, vmax=1.06, xpos=-2221.0, ypos=-784.0,
              height=60.0, width=121.68092620071866)
grid.add_bus(b11)

b12 = gce.Bus(name="Bus 12", active=True, is_slack=False, Vnom=34.82, vmin=0.94, vmax=1.06, xpos=-3079.792267299071,
              ypos=-852.9542220716496, height=60.0, width=105.89786567288775)
grid.add_bus(b12)

b13 = gce.Bus(name="Bus 13", active=True, is_slack=False, Vnom=34.66, vmin=0.94, vmax=1.06, xpos=-2669.2077327009283,
              ypos=-1030.4824002710307, height=60.0, width=113.21491672218872)
grid.add_bus(b13)

b14 = gce.Bus(name="Bus 14", active=True, is_slack=False, Vnom=34.18, vmin=0.94, vmax=1.06, xpos=-2273.016460390053,
              ypos=-1186.779596481127, height=60.0, width=118.05263642420618)
grid.add_bus(b14)

# Generators
g0 = gce.Generator(name='gen 0', active=True, P=232.4, Snom=9999, Qmin=0, Qmax=10, Pmin=0, Pmax=9999, Cost=1, vset=1.06)
grid.add_generator(b1, g0)

g1 = gce.Generator(name='gen 1', active=True, P=40, Snom=9999, Qmin=-40, Qmax=50, Pmin=0, Pmax=9999, Cost=1, vset=1.045)
grid.add_generator(b2, g1)

g2 = gce.Generator(name='gen 2', active=True, P=0, Snom=9999, Qmin=0, Qmax=40, Pmin=0, Pmax=9999, Cost=1, vset=1.01)
grid.add_generator(b3, g2)

g3 = gce.Generator(name='gen 3', active=True, P=0, Snom=9999, Qmin=-6, Qmax=24, Pmin=0, Pmax=9999, Cost=1, vset=1.07)
grid.add_generator(b6, g3)

g4 = gce.Generator(name='gen 4', active=True, P=0, Snom=9999, Qmin=-6, Qmax=24, Pmin=0, Pmax=9999, Cost=1, vset=1.09)
grid.add_generator(b8, g4)

# Shunts
sh1 = gce.Shunt(name='shunt1@Bus 9', active=True, G=0, B=19)
grid.add_shunt(bus=b9, api_obj=sh1)

# Branches
br6 = gce.Branch(name='branch 6', bus_from=b4, bus_to=b5, active=True, rate=73.7207421, mttf=0, mttr=0, r=0.01335, x=0.04211, g=0, b=0, tap=1)
grid.add_branch(br6)

br10 = gce.Branch(name='branch 10', bus_from=b6, bus_to=b11, active=True, rate=10.69597032, mttf=0, mttr=0, r=0.09498, x=0.1989, g=0, b=0, tap=1)
grid.add_branch(br10)

br11 = gce.Branch(name='branch 11', bus_from=b6, bus_to=b12, active=True, rate=9.959808441, mttf=0, mttr=0, r=0.12291, x=0.25581, g=0, b=0, tap=1)
grid.add_branch(br11)

br12 = gce.Branch(name='branch 12', bus_from=b6, bus_to=b13, active=True, rate=23.46192166, mttf=0, mttr=0, r=0.06615, x=0.13027, g=0, b=0, tap=1)
grid.add_branch(br12)

br15 = gce.Branch(name='branch 15', bus_from=b9, bus_to=b10, active=True, rate=7.114898903, mttf=0, mttr=0, r=0.03181, x=0.0845, g=0, b=0, tap=1)
grid.add_branch(br15)

br16 = gce.Branch(name='branch 16', bus_from=b9, bus_to=b14, active=True, rate=11.68127756, mttf=0, mttr=0, r=0.12711, x=0.27038, g=0, b=0, tap=1)
grid.add_branch(br16)

br17 = gce.Branch(name='branch 17', bus_from=b10, bus_to=b11, active=True, rate=5.831190013, mttf=0, mttr=0, r=0.08205, x=0.19207, g=0, b=0, tap=1)
grid.add_branch(br17)

br18 = gce.Branch(name='branch 18', bus_from=b12, bus_to=b13, active=True, rate=2.284459506, mttf=0, mttr=0, r=0.22092, x=0.19988, g=0, b=0, tap=1)
grid.add_branch(br18)

br19 = gce.Branch(name='branch 19', bus_from=b13, bus_to=b14, active=True, rate=7.586985272, mttf=0, mttr=0, r=0.17093, x=0.34802, g=0, b=0, tap=1)
grid.add_branch(br19)

# Transformers
t0 = gce.Transformer2W(name='branch 0', bus_from=b1, bus_to=b2, r=0.01938, x=0.05917, g=0, b=0.0528, tap_module=1)
grid.add_transformer2w(t0)

t1 = gce.Transformer2W(name='branch 1', bus_from=b1, bus_to=b5, r=0.05403, x=0.22304, g=0, b=0.0492, tap_module=1)
grid.add_transformer2w(t1)

t2 = gce.Transformer2W(name='branch 2', bus_from=b2, bus_to=b3, r=0.04699, x=0.19797, g=0, b=0.0438, tap_module=1)
grid.add_transformer2w(t2)

t3 = gce.Transformer2W(name='branch 3', bus_from=b2, bus_to=b4, r=0.05811, x=0.17632, g=0, b=0.034, tap_module=1)
grid.add_transformer2w(t3)

t4 = gce.Transformer2W(name='branch 4', bus_from=b2, bus_to=b5, r=0.05695, x=0.17388, g=0, b=0.0346, tap_module=1)
grid.add_transformer2w(t4)

t5 = gce.Transformer2W(name='branch 5', bus_from=b3, bus_to=b4, r=0.06701, x=0.17103, g=0, b=0.0128, tap_module=1)
grid.add_transformer2w(t5)

t7 = gce.Transformer2W(name='branch 7', bus_from=b4, bus_to=b7, r=0, x=0.20912, g=0, b=0, tap_module=0.978)
grid.add_transformer2w(t7)

t8 = gce.Transformer2W(name='branch 8', bus_from=b4, bus_to=b9, r=0, x=0.55618, g=0, b=0, tap_module=0.969)
grid.add_transformer2w(t8)

t9 = gce.Transformer2W(name='branch 9', bus_from=b5, bus_to=b6, r=0, x=0.25202, g=0, b=0, tap_module=0.932)
grid.add_transformer2w(t9)

t13 = gce.Transformer2W(name='branch 13', bus_from=b7, bus_to=b8, r=0, x=0.17615, g=0, b=0)
grid.add_transformer2w(t13)

t14 = gce.Transformer2W(name='branch 14', bus_from=b7, bus_to=b9, r=0, x=0.11001, g=0, b=0)
grid.add_transformer2w(t14)

# Loads
load1 = gce.Load(name='Load1@Bus 2', active=True, P=21.7, Q=12.7)
load2 = gce.Load(name='Load1@Bus 3', active=True, P=94.2, Q=19.0)
load3 = gce.Load(name='Load1@Bus 4', active=True, P=47.8, Q=-3.9)
load4 = gce.Load(name='Load1@Bus 5', active=True, P=7.6, Q=1.6)
load5 = gce.Load(name='Load1@Bus 6', active=True, P=11.2, Q=7.5)
load6 = gce.Load(name='Load1@Bus 9', active=True, P=29.5, Q=16.6)
load7 = gce.Load(name='Load1@Bus 10', active=True, P=9.0, Q=5.8)
load8 = gce.Load(name='Load1@Bus 11', active=True, P=3.5, Q=1.8)
load9 = gce.Load(name='Load1@Bus 12', active=True, P=6.1, Q=1.6)
load10 = gce.Load(name='Load1@Bus 13', active=True, P=13.5, Q=5.8)
load11 = gce.Load(name='Load1@Bus 14', active=True, P=14.9, Q=5.0)

grid.add_load(b2, load1)
grid.add_load(b3, load2)
grid.add_load(b4, load3)
grid.add_load(b5, load4)
grid.add_load(b6, load5)
grid.add_load(b9, load6)
grid.add_load(b10, load7)
grid.add_load(b11, load8)
grid.add_load(b12, load9)
grid.add_load(b13, load10)
grid.add_load(b14, load11)

# PowerFlow
results = gce.power_flow(grid)

print(grid.name)
print('Converged:', results.converged, 'error:', results.error)
#print(results.converged)
#print(results.get_branch_df())
#print(results.get_bus_df())
#print(results.get_report_dataframe())

nc = gce.compile_numerical_circuit_at(circuit=grid, t_idx=None)

adm = nc.get_admittance_matrices()
Sbus = nc.get_power_injections()  # MW +j MVAr
Sbus_pu = nc.get_current_injections_pu()

#print("Ybus:", adm.Ybus.todense())
print("Sbus:", Sbus)
print(abs(results.voltage))
print(np.angle(results.voltage))


print()

gce.save_file(grid, "exemple.gridcal")

'''
# Buses
b1 = gce.Bus(name="Bus 1",
             Vnom=15,
             is_slack=True)
grid.add_bus(b1)

b2 = gce.Bus(name="Bus 2",
             Vnom=345)
grid.add_bus(b2)

b3 = gce.Bus(name="Bus 3",
             Vnom=15)
grid.add_bus(b3)

b4 = gce.Bus(name="Bus 4",
             Vnom=345)
grid.add_bus(b4)

b5 = gce.Bus(name="Bus 5",
             Vnom=345)
grid.add_bus(b5)

# Generators
g1 = gce.Generator(name='g1',
                   vset=1.0,
                   Snom=400)
grid.add_generator(b1, g1)

g2 = gce.Generator(name='g2',
                   vset=1.05,
                   Snom=800,
                   Qmin=4000,
                   Qmax=-2800)
grid.add_generator(b3, g2)

# Lines
grid.add_line(gce.Line(name="l1",
                       bus_from=b4,
                       bus_to=b2,
                       rate=1200,
                       r=0.009,
                       x=0.1,
                       b=1.72,
                       length=321.8688))

grid.add_line(gce.Line(name="l2",
                       bus_from=b5,
                       bus_to=b2,
                       rate=1200,
                       r=0.0045,
                       x=0.05,
                       b=0.88,
                       length=321.8688 / 2))

grid.add_line(gce.Line(name="l3",
                       bus_from=b5,
                       bus_to=b4,
                       rate=1200,
                       r=0.00225,
                       x=0.025,
                       b=0.44,
                       length=321.8688 / 4))

# Transformador
t1 = gce.Transformer2W(name="t1",
                       bus_from=b1,
                       bus_to=b5,
                       HV=345,
                       LV=15,
                       r=0.00150,
                       x=0.02,
                       g=0,
                       b=0,
                       nominal_power=400)
grid.add_transformer2w(t1)

t2 = gce.Transformer2W(
    name="t2",
    bus_from=b3,
    bus_to=b4,
    HV=345,
    LV=15,
    r=0.00075,
    x=0.01,
    g=0,
    b=0,
    nominal_power=800,
    active=False

)
grid.add_transformer2w(t2)

# Loads
grid.add_load(b3, gce.Load("ld1", P=80, Q=40))

grid.add_load(b2, gce.Load("ld2", P=800, Q=280))

# PowerFlow
results = gce.power_flow(grid)

print(grid.name)
print('Converged:', results.converged, 'error:', results.error)
#print(results.converged)
#print(results.get_branch_df())
#print(results.get_bus_df())
#print(results.get_report_dataframe())

# gce.save_file(grid=grid, filename="ejemplo_glover_6_9.gridcal")

nc = gce.compile_numerical_circuit_at(circuit=grid, t_idx=None)

adm = nc.get_admittance_matrices()
Sbus = nc.get_power_injections()  # MW +j MVAr
Sbus_pu = nc.get_current_injections_pu()

print("Ybus:", adm.Ybus.todense())
print("Sbus:", Sbus)

print()

gce.save_file(grid, "my_file_2.gridcal")
'''
