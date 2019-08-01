from math import ceil

coords = {}

# dy : <1|-1>=inverted y direction * (<offset> + <y step>)
# dx : pow(-1, i)=x direction * ceil(i/2.0)=number of steps * <step size>
# C
def def_points(prefix, dx, dy, range):
    for i in range:
        name = '{}{}'.format(prefix, 'Z' if i == 0 else i)
        coords.update({name: (dx(i), dy(i))})

# C, T
c_dx = lambda i: pow(-1, i) * ceil(i/2.0) * 0.077
c_dy = lambda i: 0
def_points('C', c_dx, c_dy, range(7))
def_points('T', c_dx, c_dy, range(7,7+4))
def_points('A', ) # ear refs
# FC, FT
fc_dx = lambda i: pow(-1, i) * ceil(i/2.0) * 0.075
fc_dy = lambda i: -1 * (0.075 + 0.002* pow(ceil(i/2.0), 2) )
def_points('FC', fc_dx, fc_dy, range(7))
def_points('FT', fc_dx, fc_dy, range(7,7+4))
# F
f_dx = lambda i: pow(-1, i) * ceil(i/2.0) * 0.065
f_dy = lambda i: -1 * (0.15 + 0.0035* pow(ceil(i/2.0), 2) )
def_points('F', f_dx, f_dy, range(11))
# AF
af_dx = lambda i: pow(-1, i) * ceil(i/2.0) * 0.06
af_dy = lambda i: -1 * (0.23 + 0.005* pow(ceil(i/2.0), 2) )
def_points('AF', af_dx, af_dy, range(9))
# Fp
fp_dx = lambda i: pow(-1, i) * ceil(i/2.0) * 0.09
fp_dy = lambda i: -1 * (0.32 - 0.005* pow(ceil(i/2.0), 2) )
def_points('Fp', fp_dx, fp_dy, range(3))
# N
def_points('N', lambda i: 0, lambda i: -0.4, range(1))
# CP, TP
cp_dx = fc_dx
cp_dy = lambda i: -1 * fc_dy(i)
def_points('CP', cp_dx, cp_dy, range(7))
def_points('TP', cp_dx, cp_dy, range(7,7+4))
# P
p_dx = f_dx
p_dy = lambda i: -1 * f_dy(i)
def_points('P', p_dx, p_dy, range(11))
# PO
p_dx = af_dx
p_dy = lambda i: -1 * af_dy(i)
def_points('PO', p_dx, p_dy, range(9))
# O
p_dx = fp_dx
p_dy = lambda i: -1 * fp_dy(i)
def_points('O', p_dx, p_dy, range(3))
# I
def_points('I', lambda i: 0, lambda i: 0.4, range(1))

top_8c_10_20 = ['FZ', 'CZ', 'P3', 'PZ', 'P4', 'PO7', 'PO8', 'OZ' ]
