#!/usr/bin/env python3
"""Generate SGS turbulent dispersion test cases for FDS.

Creates 20 FDS input files (10 Tier 1 at 1m, 10 Tier 2 at 0.5m) that exercise
SGS turbulent dispersion models in a turbulent fire plume environment.
"""

import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Number of individually tracked particles
N_TRACKED = 20
# Total particles per case
N_TOTAL = 1000

# Case matrix: (suffix, sgs_model, turb_disp_explicit, density, burning)
CASES = [
    ('none_heavy', 0, False, 300, False),
    ('rw_heavy',   0, True,  300, False),
    ('lv_heavy',   1, None,  300, False),  # None = auto-set by SGS_MODEL>0
    ('df_heavy',   2, None,  300, False),
    ('none_light', 0, False, 50,  False),
    ('rw_light',   0, True,  50,  False),
    ('lv_light',   1, None,  50,  False),
    ('df_light',   2, None,  50,  False),
    ('lv_burn',    1, None,  100, True),   # Moderate density: more airtime than heavy, stays in domain
    ('df_burn',    2, None,  100, True),
]

RESOLUTIONS = [
    ('1m',   1.0, (40, 20, 20)),
    ('0p5m', 0.5, (80, 40, 40)),
]

# Domain: 40m x 20m x 20m
DOMAIN = (0.0, 40.0, -10.0, 10.0, 0.0, 20.0)

# SGS model names for titles
SGS_NAMES = {
    (0, False): 'no dispersion',
    (0, True):  'Markov-0 random walk',
    (1, None):  'Langevin',
    (2, None):  'differential filter',
}


def sgs_label(sgs_model, turb_disp):
    return SGS_NAMES.get((sgs_model, turb_disp), f'SGS_MODEL={sgs_model}')


def make_part_line(sgs_model, turb_disp, burning):
    """Build the &PART line with appropriate SGS parameters."""
    parts = ["&PART ID='EMBERS', SURF_ID='EMBER_SURF', DRAG_LAW='CYLINDER'"]
    if burning:
        parts.append("      EMBER_PARTICLE=.TRUE., INITIAL_TEMPERATURE=400.")
    if sgs_model > 0:
        parts.append(f"      SGS_MODEL={sgs_model}")
    elif turb_disp:
        parts.append("      TURBULENT_DISPERSION=.TRUE.")
    parts.append("      QUANTITIES(1:3)='PARTICLE U','PARTICLE V','PARTICLE W' /")
    return ',\n'.join(parts)


def make_materials(density, burning):
    """Build material and surface definitions."""
    lines = []
    if burning:
        lines.append(f"""\
&MATL ID='EMBER_WOOD'
      DENSITY={density:.0f}.
      CONDUCTIVITY=0.15
      SPECIFIC_HEAT=1.3
      N_REACTIONS=1
      REFERENCE_TEMPERATURE=500.
      SPEC_ID(1,1)='PRODUCTS'
      NU_SPEC(1,1)=0.76
      NU_MATL(1,1)=0.24
      MATL_ID(1,1)='CHAR'
      HEAT_OF_REACTION(1)=418. /

&MATL ID='CHAR'
      DENSITY=24.
      CONDUCTIVITY=0.1
      SPECIFIC_HEAT=1.0 /

&SURF ID='EMBER_SURF', MATL_ID='EMBER_WOOD', GEOMETRY='CYLINDRICAL',
      LENGTH=0.020, THICKNESS=0.0025 /""")
    else:
        lines.append(f"""\
&MATL ID='INERT_WOOD'
      DENSITY={density:.0f}.
      CONDUCTIVITY=0.15
      SPECIFIC_HEAT=1.3 /

&SURF ID='EMBER_SURF', MATL_ID='INERT_WOOD', GEOMETRY='CYLINDRICAL',
      LENGTH=0.020, THICKNESS=0.0025 /""")
    return '\n'.join(lines)


def make_init_and_devc():
    """Build INIT lines for tracked + bulk particles and DEVC lines."""
    lines = []

    # Tracked particles: individual INIT in a small cloud (0.5m cube)
    # Slightly different positions let the DF model produce different trajectories
    for i in range(1, N_TRACKED + 1):
        lines.append(f"&INIT ID='trk{i:02d}', PART_ID='EMBERS', XB=9.75,10.25,-0.25,0.25,9.75,10.25, N_PARTICLES=1 /")

    # Bulk particles
    n_bulk = N_TOTAL - N_TRACKED
    lines.append(f"&INIT ID='bulk', PART_ID='EMBERS', XB=9.5,10.5,-0.5,0.5,9.5,10.5, N_PARTICLES={n_bulk} /")

    lines.append('')

    # DEVC for tracked particles
    for i in range(1, N_TRACKED + 1):
        lines.append(f"&DEVC ID='P{i:02d}_X', QUANTITY='PARTICLE X', INIT_ID='trk{i:02d}' /")
        lines.append(f"&DEVC ID='P{i:02d}_Y', QUANTITY='PARTICLE Y', INIT_ID='trk{i:02d}' /")
        lines.append(f"&DEVC ID='P{i:02d}_Z', QUANTITY='PARTICLE Z', INIT_ID='trk{i:02d}' /")

    return '\n'.join(lines)


def make_turbulence_devc():
    """Build DEVC lines for turbulence monitoring."""
    return """\
&DEVC ID='KSGS_plume', XYZ=10.,0.,5., QUANTITY='SUBGRID KINETIC ENERGY' /
&DEVC ID='KSGS_10m', XYZ=20.,0.,10., QUANTITY='SUBGRID KINETIC ENERGY' /
&DEVC ID='KSGS_20m', XYZ=30.,0.,10., QUANTITY='SUBGRID KINETIC ENERGY' /
&DEVC ID='MU_T_plume', XYZ=10.,0.,5., QUANTITY='VISCOSITY' /
&DEVC ID='MU_T_10m', XYZ=20.,0.,10., QUANTITY='VISCOSITY' /
&DEVC ID='TMP_plume', XYZ=10.,0.,5., QUANTITY='TEMPERATURE' /
&DEVC ID='TMP_10m', XYZ=20.,0.,10., QUANTITY='TEMPERATURE' /
&DEVC ID='U_10m', XYZ=20.,0.,10., QUANTITY='U-VELOCITY' /
&DEVC ID='W_plume', XYZ=5.,0.,5., QUANTITY='W-VELOCITY' /"""


def generate_case(suffix, sgs_model, turb_disp, density, burning, res_name, dx, ijk):
    """Generate a complete FDS input file."""
    chid = f'sgs_turb_{suffix}_{res_name}'
    label = sgs_label(sgs_model, turb_disp)
    density_label = 'burning' if burning else f'{density} kg/m3'
    title = f'SGS turb dispersion: {label}, {density_label}, {res_name}'

    xb = f'{DOMAIN[0]:.0f}.,{DOMAIN[1]:.0f}.,{DOMAIN[2]:.0f}.,{DOMAIN[3]:.0f}.,{DOMAIN[4]:.0f}.,{DOMAIN[5]:.0f}.'

    content = f"""\
&HEAD CHID='{chid}', TITLE='{title}' /

&MESH IJK={ijk[0]},{ijk[1]},{ijk[2]}, XB={xb} /

&TIME T_END=60. /

&DUMP DT_DEVC=0.5, DT_PART=1.0, NFRAMES=120 /

&MISC PARTICLE_CFL=.TRUE., RND_SEED=12345 /

&WIND U0=3. /

&REAC FUEL='PROPANE', SOOT_YIELD=0.01 /

&SURF ID='FIRE', HRRPUA=500., COLOR='ORANGE' /

{make_materials(density, burning)}

{make_part_line(sgs_model, turb_disp, burning)}

{make_init_and_devc()}

&VENT XB=4.,6.,-1.,1.,0.,0., SURF_ID='FIRE' /

&VENT MB='XMIN', SURF_ID='OPEN' /
&VENT MB='XMAX', SURF_ID='OPEN' /
&VENT MB='YMIN', SURF_ID='OPEN' /
&VENT MB='YMAX', SURF_ID='OPEN' /
&VENT MB='ZMAX', SURF_ID='OPEN' /

{make_turbulence_devc()}

&SLCF PBY=0., QUANTITY='TEMPERATURE', CELL_CENTERED=.TRUE. /
&SLCF PBY=0., QUANTITY='VELOCITY', VECTOR=.TRUE. /

&TAIL /
"""
    return chid, content


def main():
    generated = []
    for suffix, sgs_model, turb_disp, density, burning in CASES:
        for res_name, dx, ijk in RESOLUTIONS:
            chid, content = generate_case(
                suffix, sgs_model, turb_disp, density, burning,
                res_name, dx, ijk)
            filepath = os.path.join(OUTPUT_DIR, f'{chid}.fds')
            with open(filepath, 'w') as f:
                f.write(content)
            generated.append(chid)
            print(f'  Created: {chid}.fds')

    print(f'\nGenerated {len(generated)} FDS input files in {OUTPUT_DIR}')
    print(f'  Tier 1 (1m):   {sum(1 for g in generated if g.endswith("_1m"))} cases')
    print(f'  Tier 2 (0.5m): {sum(1 for g in generated if g.endswith("_0p5m"))} cases')


if __name__ == '__main__':
    main()
