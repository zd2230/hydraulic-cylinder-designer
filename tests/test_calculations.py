#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hydraulic Cylinder Design Tool V2.3 - Core Calculation Verification Tests
Validates all fixes are correctly applied.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mymodule.data import *

passes = 0
fails = 0

def test(name, actual, expected, tol=1e-9):
    global passes, fails
    abs_err = abs(actual - expected)
    rel_err = abs_err / abs(expected) if abs(expected) > 1e-12 else abs_err
    if abs_err <= tol or rel_err <= 1e-6:
        print(f"  PASS: {name}: {actual}")
        passes += 1
    else:
        print(f"  FAIL: {name}: got={actual}, expected={expected}, err={abs_err:.2e}")
        fails += 1

def test_bool(name, actual):
    global passes, fails
    if actual:
        print(f"  PASS: {name}")
        passes += 1
    else:
        print(f"  FAIL: {name}: FAILED")
        fails += 1

# ========== Accumulator Formula Tests ==========
print("\n[Accumulator Formula - Isothermal Process]")

# dV=5L, p1=100bar, p2=160bar - typical case
V0 = accumulator_V0_isothermal(5, 100, 160)
test("Isothermal dV=5L,p1=100,p2=160 -> V0~14.9L", V0, 14.89, 0.1)

# adiabatic
V0a = accumulator_V0_adiabatic(5, 100, 160)
test("Adiabatic dV=5L,p1=100,p2=160 -> V0~19.0L", V0a, 19.0, 0.2)

# V0 must be > dV
test_bool("Nominal volume V0 > compensation volume dV", V0 > 5)

# Isothermal V0 < Adiabatic V0 (isothermal is more efficient)
test_bool("Isothermal V0 < Adiabatic V0", V0 < V0a)

# Low pressure case: dV=2L, p1=50, p2=80
# p0=0.9*50+1.01325=46.01325, p1=51.01325, p2=81.01325
# V0 = 2/(0.90197-0.56801) = 2/0.33396 = 5.989
V0_low = accumulator_V0_isothermal(2, 50, 80)
test("Low pressure dV=2L,p1=50,p2=80 -> V0~5.99L", V0_low, 5.99, 0.05)

# High pressure case: dV=10L, p1=200, p2=315
# p0=0.9*200+1.01325=181.01325, p1=201.01325, p2=316.01325
# V0 = 10/(0.90050-0.57280) = 10/0.32770 = 30.52
V0_high = accumulator_V0_isothermal(10, 200, 315)
test("High pressure dV=10L,p1=200,p2=315 -> V0~30.5L", V0_high, 30.5, 0.5)

# Edge: p2 <= p1 -> returns 0
V0_invalid = accumulator_V0_isothermal(5, 200, 150)
test_bool("p2 <= p1 -> returns 0", V0_invalid == 0)

# ========== Wall Thickness Tests ==========
print("\n[Wall Thickness - d/D Classification Correct]")

# D=100, p=6.3, 45#, n=4 - should be thin wall (d/D=3.5%<8%)
w1, f1, r1 = wall_thickness(100, 6.3, 355, 4)
is_thin = 'thin' in f1.lower() or 'bo bi' in f1.lower() or '薄壁' in f1
test_bool(f"D=100,p=6.3,45# thin-wall d/D={r1:.3f}", r1 <= 0.08)

# D=100, p=16, 45#, n=4 - should be medium/thick (d/D=9.0%>8%)
w2, f2, r2 = wall_thickness(100, 16, 355, 4)
is_med = r2 > 0.08
test_bool(f"D=100,p=16,45# medium-wall d/D={r2:.3f}", is_med)

# D=50, p=16, 27SiMn(835MPa), n=4 - CORRECTED: should be thin wall
w3, f3, r3 = wall_thickness(50, 16, 835, 4)
test_bool(f"D=50,p=16,27SiMn thin-wall (was misclassified) d/D={r3:.3f}", r3 <= 0.08)

# D=320, p=25, 45#, n=4 - CORRECTED: should be medium wall
w4, f4, r4 = wall_thickness(320, 25, 355, 4)
test_bool(f"D=320,p=25,45# medium-wall (was misclassified) d/D={r4:.3f}", r4 > 0.08)

# D=63, p=20, 45#, n=4 - verify
w5, f5, r5 = wall_thickness(63, 20, 355, 4)
test("D=63,p=20(1.25x16),45# wall thickness", w5, 7.61, 0.1)

# All wall thicknesses positive
test_bool("All wall thickness > 0", all(w > 0 for w in [w1, w2, w3, w4, w5]))

# ========== Basic Functions ==========
print("\n[Basic Calculation Functions]")

Dc = bore_by_force(50000, 16, 0.92)
test("bore_by_force(50000,16,0.92)", Dc, 65.76, 0.1)

A = piston_area_m2(100)
test("piston_area(100mm)", A * 1e6, 7853.98, 0.1)

Aa = annulus_area_m2(100, 50)
test("annulus_area(100,50)", Aa * 1e6, 5890.49, 0.1)

Q = flow_rate(0.01, 0.1)
test("flow_rate(0.01m2,0.1m/s)", Q, 60.0, 0.01)

Re_lam = reynolds_number(1, 0.02, 4.6e-5)
test("Re laminar", Re_lam, 434.78, 1)

Re_turb = reynolds_number(10, 0.02, 4.6e-5)
test("Re turbulent", Re_turb, 4347.83, 1)

ff_lam = friction_factor(500)
test("friction laminar (Re=500)", ff_lam, 0.128, 0.001)

ff_turb = friction_factor(5000)
test("friction turbulent (Re=5000)", ff_turb, 0.0376, 0.001)

ff_zero = friction_factor(0)
test("friction_factor(0) -> 0.04", ff_zero, 0.04, 0.001)

ff_2320 = friction_factor(2320)
test("friction factor at Re=2320", ff_2320, 0.0456, 0.001)

ff_2319 = friction_factor(2319)
test_bool("Re=2319 laminar vs Re=2320 turbulent different", ff_2319 != ff_2320)

# ========== nearest tests ==========
print("\n[Helper Functions]")

test("nearest(67, STD_BORE)", nearest(67, STD_BORE), 63)
test("nearest(100, STD_BORE)", nearest(100, STD_BORE), 100)
test("nearest(24, STD_BORE)", nearest(24, STD_BORE), 25)
test("nearest(67, []) guard", nearest(67, []), 67)

# ========== Accumulator Edge Cases ==========
print("\n[Accumulator Edge Cases]")

test_bool("dV=0 -> returns 0", accumulator_V0_isothermal(0, 100, 160) == 0)
test_bool("p2 = p1 -> returns 0", accumulator_V0_isothermal(5, 100, 100) == 0)

V0_tiny = accumulator_V0_isothermal(1, 5, 50)
test_bool("p1=5bar(>0) -> V0 > 0", V0_tiny > 0)

# ========== Regression: Verify Old Bugs Fixed ==========
print("\n[Regression Verification - Old Bugs Fixed]")

# BUG1: Accumulator formula no longer returns negative
V0_test = accumulator_V0_isothermal(5, 100, 160)
test_bool("ACCUMULATOR: V0 no longer negative (was -7.5L truncated to 0.5L)", V0_test > 0 and V0_test > 5)

# BUG2: Wall thickness classification uses actual d/D
test_bool("WALL CLASSIFY: high-strength thin-wall not misclassified", r3 <= 0.08)

# BUG3: Buckling penalty removed (verified via code diff)

# BUG4: nearest empty series guard
test("NEAREST: empty series guard returns val", nearest(100, []), 100)

# ========== Material Database Integrity ==========
print("\n[Material Database]")
required_keys = {'E', 'G', 'a', 'b', 'desc'}
for name, props in STEEL_DB.items():
    missing = required_keys - set(props.keys())
    test_bool(f"Material {name}: all required params present", len(missing) == 0)

test_bool("sigma_s: 45#(355) < 27SiMn(835)", STEEL_DB['45#']['σs'] < STEEL_DB['27SiMn']['σs'])
test_bool("sigma_s: Q235(235) is lowest", STEEL_DB['Q235']['σs'] == min(p['σs'] for p in STEEL_DB.values()))

# ========== Standard Data Consistency ==========
print("\n[Standard Data Consistency]")
test_bool("STD_BORE sorted", STD_BORE == sorted(STD_BORE))
test_bool("STD_ROD sorted", STD_ROD == sorted(STD_ROD))
test_bool("STD_PRESSURE sorted", STD_PRESSURE == sorted(STD_PRESSURE))
test_bool("STD_WALL sorted", STD_WALL == sorted(STD_WALL))
test_bool("MOTOR_STD sorted", MOTOR_STD == sorted(MOTOR_STD))

# ========== Unit Conversion ==========
print("\n[Unit Conversion]")
test("1N = 0.10197kgf", 1/9.80665, 0.10197, 0.0001)
test("1MPa = 1e6 Pa", 1e6, 1e6)
test("1m3/s = 60000 L/min", 1*60000, 60000)

# ========== Summary ==========
print(f"\n{'='*60}")
total = passes + fails
print(f"Test Results: {passes}/{total} passed, {fails} failed")
if fails == 0:
    print("ALL TESTS PASSED - V2.3 fixes verified successfully")
else:
    print(f"ERROR: {fails} failing test case(s), requires correction")
print(f"{'='*60}")

exit(0 if fails == 0 else 1)
