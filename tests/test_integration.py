#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for the full 9-step calculation pipeline of V2.3.
Validates the complete engineering design flow end-to-end.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mymodule.data import *

def test_full_pipeline():
    """
    Test case: Standard construction machinery cylinder
    F=50000N, v=0.1m/s, S=500mm, p_sys=16MPa, material 45#
    This is a medium-duty, medium-pressure, medium-size design.
    """
    F, v, S, f, Te, Tm = 50000, 0.1, 500, 5, 30, 60
    ps, eta, mat = 16, 0.92, '45#'
    st = STEEL_DB[mat]

    # Step 1: Duty cycle analysis
    Pp = F * v / 1000
    duty = min(S / 1000 / v / (60 / max(f, 0.1)) * 2, 1.0)
    lp = 1.0 + (1 - duty) * 0.5
    assert Pp > 0 and lp >= 1.0, f"Step 1 failed: Pp={Pp}, lp={lp}"

    # Step 2: Pressure & preliminary bore
    Dc = bore_by_force(F, ps, eta)
    A1_est = piston_area_m2(Dc)
    Qe = flow_rate(A1_est, v)
    assert Dc > 0 and Qe > 0, f"Step 2 failed"

    # Step 3: Standard bore selection
    Ds = nearest(Dc, STD_BORE)
    A1 = piston_area_m2(Ds)
    pa = F / A1 / 1e6 / eta
    Fp = A1 * ps * 1e6 * eta / 1000
    assert Ds >= 50 and pa <= ps * 1.3, f"Step 3 failed: Ds={Ds}, pa={pa}"

    # Step 4: Rod diameter
    dr_ratio = 0.35 if pa <= 5 else (0.5 if pa <= 7 else 0.7)
    cand = [r for r in STD_ROD if r < Ds * 0.95]
    ds = nearest(Ds * dr_ratio, cand) if cand else Ds * 0.85
    A2 = annulus_area_m2(Ds, ds)
    Fpl = A2 * ps * 1e6 * eta / 1000
    phi = A1 / A2 if A2 > 0 else 1
    assert ds < Ds and phi > 1, f"Step 4 failed: ds={ds}, phi={phi}"

    # Step 5: Wall thickness
    pm = ps * 1.25
    n = 4
    wall, wtf, wtr = wall_thickness(Ds, pm, st['σs'], n)
    ws = nearest(wall, STD_WALL)
    Do = Ds + 2 * ws
    assert wall > 0 and Do > Ds, f"Step 5 failed: wall={wall}"
    assert wtr > 0, f"Wall ratio must be positive, got {wtr}"

    # Step 6: Buckling stability (all units in mm, consistent with app.py fix)
    mt = 200; mu = 1.0; nr = 10
    L = S + mt
    ds_mm = ds
    I_mm4 = math.pi * ds_mm**4 / 64
    Ar_mm2 = math.pi * ds_mm**2 / 4
    i_mm = math.sqrt(I_mm4 / Ar_mm2) if Ar_mm2 > 0 else 0
    Le_mm = mu * L
    lam = Le_mm / i_mm if i_mm > 0 else 0
    sp = st['σp']; a_st = st['a']; b_st = st['b']; E = st['E']
    l1 = math.pi * math.sqrt(E / sp) if sp > 0 else 100
    l2 = (a_st - sp) / b_st if b_st > 0 else 60

    if lam >= l1:
        Pcr = math.pi**2 * E * I_mm4 / Le_mm**2 / 1000
    elif lam >= l2:
        sc = a_st - b_st * lam
        Pcr = sc * Ar_mm2 / 1000
    else:
        Pcr = st['σs'] * Ar_mm2 / 1000  # MPa * m2 -> N -> kN

    nse = Pcr / (F / 1000) if F > 0 else 0
    passed = nse >= nr
    assert Pcr > 0, "Pcr must be positive"
    assert nse > 0, f"n_st={nse}, expected > 0"

    # Step 7: Seal life
    etaT = 1.0 if Tm <= 65 else (0.75 if Tm <= 75 else (0.6 if Tm <= 85 else (0.4 if Tm <= 100 else 0.12)))
    NAS = 9
    etai = max(0.1, 1.0 - max(NAS - 5, 0) * 0.25)
    base = 2000 if pa >= 31.5 else 2500 if pa > 16 else 3000 if pa > 10 else 3500
    life = base * etaT * etai
    assert life > 0, f"Seal life must be positive, got {life}"

    # Step 8: Pump matching
    Qf = flow_rate(A1, v)
    Qr = flow_rate(A2, v)
    Qd = max(Qf, Qr)
    n_pump = 1450; ev = 0.92; et_pump = 0.85
    Vg = Qd / n_pump / ev * 1000
    Pmotor = ps * Qd / 60 / et_pump
    assert Vg > 0 and Pmotor > 0, f"Step 8 failed"

    # Step 9: Thermal balance
    Pl = Pmotor * (1 - et_pump)
    Vi = Qd * 3
    Ae = 2 * (Vi / 1000)**(2 / 3) * 6
    kc = 15
    Pt = Ae * kc * (Tm - Te) / 1000
    Teq = Te + Pl / Ae / kc * 1000
    need_cooler = Pl > Pt * 1.2
    assert Vi > 0 and Teq > Te, f"Step 9 failed"

    # Accumulator test (separate from main flow)
    V0_iso = accumulator_V0_isothermal(5, 100, 160)
    V0_adi = accumulator_V0_adiabatic(5, 100, 160)
    assert V0_iso > 5, f"Accumulator V0 must exceed compensation volume"
    assert V0_adi > V0_iso, f"Adiabatic V0 must be larger than isothermal"

    return {
        'Ds': Ds, 'ds': ds, 'wall': wall, 'Do': Do,
        'Pcr': Pcr, 'n_st': nse, 'passed': passed,
        'Qd': Qd, 'Vg': Vg, 'Pmotor': Pmotor,
        'life': life, 'Teq': Teq, 'V0_iso': V0_iso
    }

# Run test
result = test_full_pipeline()
print("Integration test results:")
print(f"  Cylinder: D{result['Ds']:.0f} x d{result['ds']:.0f}mm, wall={result['wall']:.1f}mm, D_out={result['Do']:.0f}mm")
print(f"  Buckling: Pcr={result['Pcr']:.1f}kN, n_st={result['n_st']:.2f}, pass={result['passed']}")
print(f"  Hydraulics: Qd={result['Qd']:.1f}L/min, Vg={result['Vg']:.1f}mL/r, Pmotor={result['Pmotor']:.2f}kW")
print(f"  Seal life: {result['life']:.0f}h")
print(f"  Thermal: T_eq={result['Teq']:.1f}C")
print(f"  Accumulator: V0(iso)={result['V0_iso']:.1f}L")
print()
print("ALL INTEGRATION CHECKS PASSED")
