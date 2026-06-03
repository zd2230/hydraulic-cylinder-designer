#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
液压缸选型设计工具 V2.3 - 标准数据库
"""
import math

# 标准系列
STD_BORE=[25,32,40,50,63,80,90,100,110,125,140,160,180,200,220,250,280,320,360,400]
STD_ROD=[12,14,16,18,20,22,25,28,32,36,40,45,50,56,63,70,80,90,100,110,125,140,160,180,200,220,250,280,320,360]
STD_PRESSURE=[6.3,10,16,25,31.5,40]
STD_WALL=[2.0,2.5,3.0,3.5,4.0,5.0,6.0,7.0,8.0,9.0,10.0,12.0,14.0,16.0,18.0,20.0,22.0,25.0,28.0,30.0,35.0,40.0]

STEEL_DB={
    "45#":{"σs":355,"σb":600,"σ-1":200,"σp":300,"E":206000,"G":79000,"a":461,"b":2.568,"desc":"优质碳素钢·最常用·性价比高"},
    "27SiMn":{"σs":835,"σb":980,"σ-1":430,"σp":690,"E":206000,"G":79000,"a":962,"b":5.128,"desc":"合金钢·高压缸专用·焊接需预热"},
    "35#":{"σs":315,"σb":530,"σ-1":160,"σp":260,"E":206000,"G":79000,"a":461,"b":2.2,"desc":"优质碳素钢·中低压·焊接性好"},
    "Q235":{"σs":235,"σb":375,"σ-1":120,"σp":200,"E":206000,"G":79000,"a":304,"b":1.12,"desc":"普通碳素钢·低压件·成本最低"},
    "Q345":{"σs":345,"σb":510,"σ-1":180,"σp":280,"E":206000,"G":79000,"a":461,"b":2.568,"desc":"低合金钢·综合性能好"},
    "40Cr":{"σs":785,"σb":900,"σ-1":400,"σp":640,"E":206000,"G":79000,"a":461,"b":5.28,"desc":"合金钢·高疲劳·常用于活塞杆"},
    "35CrMo":{"σs":835,"σb":985,"σ-1":430,"σp":690,"E":206000,"G":79000,"a":461,"b":5.1,"desc":"铬钼钢·高温高压·淬透性好"},
    "38CrMoAl":{"σs":835,"σb":980,"σ-1":440,"σp":670,"E":206000,"G":79000,"a":461,"b":2.568,"desc":"氮化钢·活塞杆氮化耐磨极佳"},
    "ZG270-500":{"σs":270,"σb":500,"σ-1":130,"σp":220,"E":200000,"G":77000,"a":380,"b":1.5,"desc":"铸钢·缸底/缸头铸造件"},
}

PRESSURE_INFO={6.3:"低压→轻载：农机·辅机·夹具",10:"中低压→一般机械：塑料机·轻工",16:"★最常用→通用液压：工程机械·注塑机·折弯机",25:"高压→重型机械：挖掘机(≤50t)·起重机",31.5:"超高压→特重型：大型挖掘机(>50t)·矿山",40:"极高压力→特殊领域：金刚石压机"}
VALVE_DATA={"NG6 (通径6mm)":{"Q_max":40,"desc":"小型电磁换向阀·Q≤40L/min"},"NG10 (通径10mm) ★最常用":{"Q_max":100,"desc":"标准换向阀/比例阀·Q≤100L/min"},"NG16 (通径16mm)":{"Q_max":250,"desc":"中型管式+板式阀·Q≤250L/min"},"NG25 (通径25mm)":{"Q_max":500,"desc":"大型管式/插装阀·Q≤500L/min"},"NG32 (通径32mm)":{"Q_max":800,"desc":"超大流量插装/法兰阀·Q≤800L/min"},"NG40 (通径40mm)":{"Q_max":1200,"desc":"特大型法兰安装·Q≤1200L/min"}}
SEAL_TYPES=["斯特封(活塞)+格莱圈(杆)+防尘圈·中低压(p<16MPa)","组合密封+支承环+斯特封·高压(16≤p<31.5MPa)","金属密封/特殊PTFE组合·超高压(p≥31.5MPa)","V型夹布密封+O圈·低压往复(p<10MPa)","U形圈+挡圈(双作用)·工程机械(p<21MPa)","活塞环(金属环)·无密封圈设计(p<35MPa)","车氏密封+斯特封·高速往复摩擦小(p<40MPa)"]
BUFFER_TYPES=["无需缓冲 (v≤0.1m/s)","固定节流缓冲 (0.1<v≤0.3m/s)","可调缓冲阀 (v>0.3m/s·高速大惯量)","多级缓冲 (v>0.5m/s或大质量)"]
ACC_TYPES=["不选用蓄能器","囊式蓄能器·标准选择·响应快·容积0.5-200L","活塞式蓄能器·大容积(>50L)·高压力(≤35MPa)","隔膜式蓄能器·小容积·响应最快·用于脉冲吸收"]
COOLER_TYPES={"风冷散热器":25,"水冷管壳式":350,"板式换热器":500,"冷板式":200}
MOTOR_STD=[0.55,0.75,1.1,1.5,2.2,3.0,4.0,5.5,7.5,11,15,18.5,22,30,37,45,55,75,90,110,132,160,200,250,315]
PUMP_TYPES=["系统自动推荐（按Vg匹配）","齿轮泵·p≤21MPa·1~50mL/r·1000~3000rpm","叶片泵·p≤21MPa·6~237mL/r·600~1800rpm","柱塞泵·p≤35MPa·10~500mL/r·1000~3000rpm★推荐","双联泵·大流量差动·节能"]

def nearest(val,series):
    if not series: return val
    return min(series,key=lambda x:abs(x-val))

def accumulator_V0_isothermal(dV_L, p1_bar, p2_bar):
    """蓄能器公称容积(等温过程,n=1)
    dV_L: 补偿油量(L)
    p1_bar: 最低工作压力(bar,表压)
    p2_bar: 最高工作压力(bar,表压)
    返回: V0(L) — 按等温气体定律 p0*V0 = p1*V1 = p2*V2
    参考: 《现代液压气动手册》2024 第32章 蓄能器选型
    """
    p_atm = 1.01325  # 标准大气压(bar)
    p0_abs = p1_bar * 0.9 + p_atm  # 充气压力≈0.9×最低工作压力(绝对)
    p1_abs = p1_bar + p_atm
    p2_abs = p2_bar + p_atm
    if p2_abs <= p1_abs or p1_abs <= p0_abs:
        return 0
    return dV_L / (p0_abs / p1_abs - p0_abs / p2_abs)

def accumulator_V0_adiabatic(dV_L, p1_bar, p2_bar, gamma=1.4):
    """蓄能器公称容积(绝热过程,γ≈1.4 for N₂)
    适用于快速充放油(t<1min)的工况
    """
    p_atm = 1.01325
    p0_abs = p1_bar * 0.9 + p_atm
    p1_abs = p1_bar + p_atm
    p2_abs = p2_bar + p_atm
    if p2_abs <= p1_abs or p1_abs <= p0_abs:
        return 0
    return dV_L / ((p0_abs / p1_abs) ** (1 / gamma) - (p0_abs / p2_abs) ** (1 / gamma))

def wall_thickness(D_mm, p_max_MPa, sigma_s_MPa, n_safety):
    """缸筒壁厚计算(GB/T 8713 / IEC 60204 机械安全)
    D_mm: 缸筒内径(mm)
    p_max_MPa: 最大工作压力(MPa,含冲击)
    sigma_s_MPa: 材料屈服强度(MPa)
    n_safety: 安全系数
    返回: (壁厚mm, 公式类型str, 壁厚比float)

    先用薄壁公式估算,再根据δ/D比值确定最终公式:
      δ/D ≤ 0.08 → 薄壁公式 δ = pD/(2[σ])
      0.08 < δ/D ≤ 0.4 → 中厚壁(Lamé)公式
      否则 → 厚壁(安全系数×1.5保守处理)
    """
    sigma_allow = sigma_s_MPa / n_safety
    # 先用薄壁公式估算壁厚,检查壁厚/缸径比
    wall_thin = p_max_MPa * D_mm / (2 * sigma_allow)
    ratio = wall_thin / D_mm

    if ratio <= 0.08:
        return wall_thin, "薄壁公式 (δ/D ≤ 0.08)", ratio
    elif ratio <= 0.4:
        import math
        wall_lame = D_mm / 2 * (math.sqrt((sigma_allow + 0.4 * p_max_MPa) / (sigma_allow - 1.3 * p_max_MPa)) - 1)
        return wall_lame, "中厚壁(Lamé)公式 (0.08 < δ/D ≤ 0.4)", ratio
    else:
        wall_thick = wall_thin * 1.5
        return wall_thick, f"厚壁保守处理 (δ/D > 0.4, 系数1.5)", ratio

def bore_by_force(F,p_MPa,eta=0.92):
    """F(N), p_MPa(兆帕), eta(机械效率) → 缸径(mm)"""
    if p_MPa<=0 or eta<=0: return 0
    p_pa = p_MPa * 1e6  # MPa → Pa
    return math.sqrt(4*F/math.pi/p_pa/eta)*1000

def piston_area_m2(D): return math.pi*(D/1000)**2/4
def annulus_area_m2(D,d): return math.pi*((D/1000)**2-(d/1000)**2)/4
def flow_rate(A_m2,v_ms): return A_m2*v_ms*60000
def inertia_moment(d_m): return math.pi*d_m**4/64
def reynolds_number(v,d,nu=4.6e-5):
    if nu<=0: return 0
    return v*d/nu
def friction_factor(Re):
    if Re<=0: return 0.04
    if Re<2320: return 64/Re
    return 0.3164/Re**0.25
