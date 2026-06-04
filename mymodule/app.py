#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
液压缸选型设计工具 V2.3 - 主应用 + 页面
单模块架构，避免循环导入

V2.3 修复(2026-06-03):
- [致命] 蓄能器公式从 p1/p0-p2/p0 修正为标准等温/绝热公式,使用绝对压力
- [致命] 稳定性校核三公式(欧拉/Tetmajer/屈服)统一使用mm单位制,修复m²·N/mm²混用
- [高] 壁厚分类从 p/D 比值改为实际 δ/D 比值判断薄壁/厚壁
- [中] 移除压杆稳定性非标准 L/d>15 惩罚因子
- [中] 恢复项目时异常不再静默吞没
- [中] 密封基础寿命增加更多压力等级分段
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json, os, math
from datetime import datetime

from mymodule.config import *
from mymodule.data import *
from mymodule.widgets import *

PROJECT_EXT = ".hydproj"

# ==================== 安全调用包装 ====================
def safe(fn, app):
    """包装按钮回调，异常时弹窗提示而非静默失败"""
    def wrapper():
        try:
            fn(app)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            messagebox.showerror("计算错误", f"{e}\n\n{tb[:500]}")
    return wrapper

# ==================== 中文帮助函数 ====================
def pretty_delta(delta):
    """偏差百分比的中文描述"""
    s = f"偏大{delta:.0f}%" if delta>0 else f"偏小{abs(delta):.0f}%"
    return s

# ==================== 数据 ====================
def _fresh_data():
    return dict(
        F_N=0,F_kgf=0,F_ton=0,v_max=0,S_mm=0,f_cycle=1,
        P_peak_kW=0,lambda_p=0,T_env=30,T_max=60,
        p_sys=16,eta_m=0.92,valve_sel="",Q_valve_max=0,
        use_acc="no",acc_type="",acc_V0=0,
        D_calc=0,D_std=0,D_custom=0,use_custom_D=False,
        p_actual=0,A_piston_mm2=0,
        d_calc=0,d_std=0,d_custom=0,use_custom_d=False,
        F_push=0,F_pull=0,phi=1,
        wall_calc=0,wall_std=0,D_out=0,n_safety=4,
        material="45#",sigma_s=355,
        L_rod=0,lam=0,Pcr=0,n_st=0,buckle_pass=False,
        seal_type=SEAL_TYPES[0],eta_T=1,eta_iso=1,seal_life=0,
        buffer_type=BUFFER_TYPES[0],
        Q_fwd=0,Q_ret=0,Q_design=0,Vg_pump=0,P_motor=0,
        d_pipe=0,v_pipe=0,Re=0,dp_total=0,P_loss=0,
        V_tank=0,P_tank=0,need_cooler=False,
        A_cooler=0,cooler_type="",T_eq=0,pump_rec="",step=0,
    )

# ==================== 应用主类 ====================
class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title("液压缸选型设计工具 V2.3")
        self.root.geometry("1440x860")
        self.root.minsize(1200,700)
        self.root.configure(bg=C_BG)
        self.data=_fresh_data()
        self._build()
        self.run()

    # ---------- 数据 ----------
    def _collect(self):
        d=self.data
        d["F_N"]=self.s1_F.getf(0);d["v_max"]=self.s1_v.getf(0)
        d["S_mm"]=self.s1_S.getf(0);d["f_cycle"]=self.s1_f.getf(1)
        d["T_env"]=self.s1_Te.getf(30);d["T_max"]=self.s1_Tm.getf(60)
        try: d["p_sys"]=float(self.pv.get())
        except: d["p_sys"]=16
        d["eta_m"]=self.s2_eta.getf(0.92)
        d["valve_sel"]=self.vv.get()
        vk=self.vv.get()
        if vk in VALVE_DATA: d["Q_valve_max"]=VALVE_DATA[vk]["Q_max"]
        d["use_acc"]=self.acc_use.get();d["acc_type"]=self.acc_tv.get()
        d["D_custom"]=self.s3_cD.getf(0);d["d_custom"]=self.s4_cd.getf(0)
        d["F_pr"]=self.s4_Fpr.getf(0)
        d["material"]=self.s5_m.get() if self.s5_m.get() else "45#"
        d["n_safety"]=self.s5_n.getf(4)
        d["mount_type"]=self.s6_mt_cb.get()
        d["mu_val"]=self.s6_mu.getf(1.0);d["mount_allowance"]=self.s6_ma.getf(200)
        d["n_st_req"]=self.s6_nr.getf(10)
        d["seal_type"]=self.s7_s.get();d["buffer_type"]=self.s7_b.get()
        d["NAS_level"]=self.s7_NAS.getf(9)
        d["pump_type"]=self.s8_pt.get();d["pump_n"]=self.s8_n.getf(1450)
        d["pump_ev"]=self.s8_ev.getf(0.92);d["pump_et"]=self.s8_et.getf(0.85)
        d["L_pipe"]=self.s8_Lp.getf(10);d["zeta"]=self.s8_zt.getf(5)
        d["V_tank"]=self.s9_V.getf(0);d["k_tank"]=self.s9_k.getf(15)
        d["altitude_factor"]=self.s9_al.getf(1)

    def _gk(self,k,default=0):
        return self.data.get(k,default)

    def _restore(self):
        d=self.data
        try:
            self.s1_F.set(d.get("F_N",0),0);self.s1_v.set(d.get("v_max",0),3)
            self.s1_S.set(d.get("S_mm",0),0);self.s1_f.set(d.get("f_cycle",1),0)
            self.s1_Te.set(d.get("T_env",30),0);self.s1_Tm.set(d.get("T_max",60),0)
            fv=d.get("F_N",0)
            if fv: self.s1_kgf.config(text=f"{fv/9.80665:.2f}");self.s1_ton.config(text=f"{fv/9806.65:.4f}")
            self.pv.set(str(d.get("p_sys",16)));self.s2_eta.set(d.get("eta_m",0.92),2)
            vk=d.get("valve_sel","")
            if vk in VALVE_DATA: self.vv.set(vk)
            self.acc_use.set(d.get("use_acc","no"))
            self.s3_cD.set(d.get("D_custom",0),0);self.s4_cd.set(d.get("d_custom",0),0)
            self.s4_Fpr.set(d.get("F_pr",0),0)
            mat=d.get("material","45#")
            if mat in STEEL_DB: self.s5_m.set(mat)
            self.s5_n.set(d.get("n_safety",4),0)
            mt=d.get("mount_type","两端铰支(耳环安装)  μ=1.0  ★最常见")
            self.s6_mt_cb.set(mt);self.s6_mu.set(d.get("mu_val",1.0),1)
            self.s6_ma.set(d.get("mount_allowance",200),0);self.s6_nr.set(d.get("n_st_req",10),0)
            sk=d.get("seal_type",SEAL_TYPES[0])
            if sk in SEAL_TYPES: self.s7_s.set(sk)
            bk=d.get("buffer_type",BUFFER_TYPES[0])
            if bk in BUFFER_TYPES: self.s7_b.set(bk)
            self.s7_NAS.set(d.get("NAS_level",9),0)
            pk=d.get("pump_type",PUMP_TYPES[0])
            if pk in PUMP_TYPES: self.s8_pt.set(pk)
            self.s8_n.set(d.get("pump_n",1450),0);self.s8_ev.set(d.get("pump_ev",0.92),2)
            self.s8_et.set(d.get("pump_et",0.85),2);self.s8_Lp.set(d.get("L_pipe",10),0)
            self.s8_zt.set(d.get("zeta",5),0);self.s9_V.set(d.get("V_tank",0),0)
            self.s9_k.set(d.get("k_tank",15),0);self.s9_al.set(d.get("altitude_factor",1.0),1)
            self._nav()
            # 自动重算
            if d.get("F_N",0)>0:
                for fn in [c1,c2,c2a,c3,c4,c5,c6,c7,c8,c9]:
                    try: fn(self)
                    except Exception as e:
                        messagebox.showwarning("恢复重算",f"步骤计算异常: {e}")
        except Exception as e:
            messagebox.showwarning("恢复",f"部分异常: {e}")

    # ---------- UI 构建 ----------
    def _build(self):
        # 顶部栏
        tb=tk.Frame(self.root,bg=C_PANEL,highlightbackground=C_BORDER,highlightthickness=1)
        tb.pack(fill="x")
        tk.Label(tb,text="液压缸选型设计工具 V2.2",bg=C_PANEL,fg=C_ACCENT,font=F(18,True)).pack(side="left",padx=16,pady=8)
        tk.Label(tb,text="《现代液压气动手册》2024 | GB/T 2348/2349/2346",bg=C_PANEL,fg=C_TEXT2,font=F(9)).pack(side="left",padx=10)
        self.step_lb=tk.Label(tb,text="● 步骤 1/9  工况分析",bg=C_PANEL,fg=C_TEXT2,font=F(9,True))
        self.step_lb.pack(side="right",padx=16)

        # 导航
        nav=tk.Frame(self.root,bg=C_BG);nav.pack(fill="x",padx=8,pady=4)
        sn=[("1","工况"),("2","压力阀"),("2a","蓄能器"),("3","缸径"),("4","杆径"),
            ("5","壁厚"),("6","稳定"),("7","密封"),("8","泵阀"),("9","热平衡"),("✓","报告")]
        self.btns=[]
        for i,(n,t) in enumerate(sn):
            b=tk.Button(nav,text=f" {n} {t} ",anchor="center",bg=C_PANEL,fg=C_TEXT,
                        font=F(9),relief="flat",padx=6,pady=2,cursor="hand2",
                        command=lambda i=i:self._sw(i))
            b.pack(side="left",padx=2);self.btns.append(b)
        nr=tk.Frame(nav,bg=C_BG);nr.pack(side="right")
        self.bp=tk.Button(nr,text="◀ 上一步",command=self._prev,bg=C_PANEL,fg=C_TEXT,
                          font=F(9),relief="flat",padx=10,pady=2,cursor="hand2")
        self.bp.pack(side="left",padx=4)
        self.bn=tk.Button(nr,text="下一步 ▶",command=self._next,bg=C_ACCENT,fg="white",
                          font=F(9,True),relief="flat",padx=14,pady=2,cursor="hand2")
        self.bn.pack(side="left",padx=4)

        # 状态
        sf=tk.Frame(self.root,bg=C_BG);sf.pack(fill="x",padx=8,pady=(0,2))
        self.st=tk.StringVar(value="就绪")
        tk.Label(sf,textvariable=self.st,bg=C_BG,fg=C_TEXT2,font=F(9)).pack(side="left")

        # 内容
        self.cf=tk.Frame(self.root,bg=C_BG);self.cf.pack(fill="both",expand=True)

        # 构建每个页面
        self.sfs=[]
        for builder in [b1,b2,b2a,b3,b4,b5,b6,b7,b8,b9,bR]:
            sf=ScrollFrame(self.cf)
            builder(sf.scroll_frame,self)
            sf.pack(fill="both",expand=True)
            sf.pack_forget()
            self.sfs.append(sf)

        self.cur=0
        self._show(0)
        self._menu()
        self.root.bind("<Control-Right>",lambda e:self._next())
        self.root.bind("<Control-Left>",lambda e:self._prev())
        self.root.bind("<Control-n>",lambda e:self._new())
        self.root.bind("<Control-o>",lambda e:self._open())
        self.root.bind("<Control-s>",lambda e:self._save())

    def _menu(self):
        mb=tk.Menu(self.root)
        fm=tk.Menu(mb,tearoff=0)
        fm.add_command(label="新建项目",command=self._new,accelerator="Ctrl+N")
        fm.add_command(label="打开项目...",command=self._open,accelerator="Ctrl+O")
        fm.add_command(label="保存项目",command=self._save,accelerator="Ctrl+S")
        fm.add_separator()
        fm.add_command(label="导出报告...",command=self._savr)
        fm.add_separator()
        fm.add_command(label="退出",command=self.root.quit)
        mb.add_cascade(label="文件",menu=fm)
        self.root.config(menu=mb)

    def _show(self,i):
        for s in self.sfs: s.pack_forget()
        self.sfs[i].pack(fill="both",expand=True)
        self.cur=i
        self._nav()
        ns=["工况分析","压力与阀门","蓄能器(可选)","缸径计算","杆径与速比",
            "壁厚材料","稳定性校核","密封缓冲","泵阀匹配","热平衡","选型报告"]
        self.step_lb.config(text=f"● 步骤 {min(i+1,9)}/9  {ns[i] if i<len(ns) else ''}")
        if i==len(self.sfs)-1:
            self.root.after(100, safe(gR, self))

    def _sw(self,i):
        if 0<=i<len(self.sfs): self._show(i)
    def _next(self):
        if self.cur<len(self.sfs)-1: self._show(self.cur+1)
    def _prev(self):
        if self.cur>0: self._show(self.cur-1)

    def _nav(self):
        for i,s in enumerate(self.sfs):
            d=self._done(i)
            b=self.btns[i]
            if i==self.cur: b.config(bg=C_ACCENT,fg="white",font=F(9,True))
            elif d: b.config(bg=C_GREEN,fg="white",font=F(9,True))
            else: b.config(bg=C_PANEL,fg=C_TEXT,font=F(9))

    def _done(self,i):
        km={0:"F_N",1:"p_sys",2:"p_sys",3:"D_std",4:"d_std",5:"wall_std",
            6:"lam",7:"seal_type",8:"Q_design",9:"P_loss"}
        k=km.get(i)
        if not k: return False
        v=self.data.get(k,0)
        return bool(v) if isinstance(v,str) else v>0

    def msg(self,t): self.st.set(t)

    # 文件
    def _new(self):
        if messagebox.askyesno("新建","清除所有数据重新开始？"):
            self.data=_fresh_data();self._restore();self.msg("已重置")
    def _save(self):
        self._collect()
        fp=filedialog.asksaveasfilename(defaultextension=PROJECT_EXT,
            filetypes=[("液压缸项目",f"*{PROJECT_EXT}"),("所有","*.*")],title="保存")
        if not fp: return
        try:
            s={}
            for k,v in self.data.items():
                if v is None: s[k]=None
                elif isinstance(v,(str,int,float,bool,list)): s[k]=v
                else: s[k]=str(v)
            with open(fp,"w",encoding="utf-8") as f: json.dump(s,f,ensure_ascii=False,indent=2)
            self.msg(f"已保存 {os.path.basename(fp)}")
        except Exception as e: messagebox.showerror("错误",str(e))
    def _open(self):
        fp=filedialog.askopenfilename(filetypes=[("液压缸项目",f"*{PROJECT_EXT}"),("所有","*.*")],title="打开")
        if not fp: return
        try:
            with open(fp,"r",encoding="utf-8") as f: self.data.update(json.load(f))
            self._restore();self.msg(f"已加载 {os.path.basename(fp)}")
        except Exception as e: messagebox.showerror("错误",str(e))
    def _savr(self):
        fp=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("文本","*.txt"),("所有","*.*")],title="保存报告")
        if not fp: return
        try:
            with open(fp,"w",encoding="utf-8") as f: f.write(self.rt.get("1.0","end"))
            self.msg(f"报告已保存")
        except Exception as e: messagebox.showerror("错误",str(e))

    def run(self): self.root.mainloop()


# ==================== 页面构建函数 ====================
def b1(p,app):
    """步骤1 工况分析"""
    step_title(p,"步骤 1：工况与负载分析","Load & Motion Analysis")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="填写液压缸使用需求，系统自动换算负载单位(N→kgf→t)",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")

    c=Card(p,"负载与运动参数");c.pack(fill="x",padx=10,pady=4)
    app.s1_F=InpRow(c,"最大负载力 F_max","N","","液压缸需克服的最大外力(含加速度惯性力)")
    app.s1_F.pack(fill="x",pady=2)
    r1=tk.Frame(c,bg=C_PANEL);r1.pack(fill="x",pady=2)
    app.s1_kgf=tk.Label(r1,text="--",bg=C_PANEL,fg=C_ACCENT2,font=F(10,True))
    app.s1_ton=tk.Label(r1,text="--",bg=C_PANEL,fg=C_ACCENT2,font=F(10,True))
    tk.Label(r1,text="  =  kgf  ",bg=C_PANEL,fg=C_TEXT2,font=F()).pack(side="left")
    app.s1_kgf.pack(side="left",padx=2)
    tk.Label(r1,text="  =  吨(t)",bg=C_PANEL,fg=C_TEXT2,font=F()).pack(side="left")
    app.s1_ton.pack(side="left",padx=2)

    def _of(*a):
        f=app.s1_F.getf(0)
        if f>0: app.s1_kgf.config(text=f"{f/9.80665:.2f}");app.s1_ton.config(text=f"{f/9806.65:.4f}")
        else: app.s1_kgf.config(text="--");app.s1_ton.config(text="--")
    app.s1_F.var.trace_add("write",_of)

    sp=tk.Frame(c,bg=C_PANEL);sp.pack(fill="x",pady=2)
    tk.Label(sp,text="速度典型值",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.s1_vp=ttk.Combobox(sp,values=["重型压机 0.02","轻载压机 0.05","慢速送料 0.08",
        "工程机械 0.10 ★常用","行走机械 0.15","高速机床 0.30","快速推送 0.50"],
        state="readonly",font=F(),width=20)
    app.s1_vp.pack(side="left",padx=2)
    app.s1_vp.bind("<<ComboboxSelected>>",lambda e:_set_v(app))
    app.s1_v=InpRow(c,"最高速度 v_max(可自定义)","m/s","","工程机械0.05-0.3");app.s1_v.pack(fill="x",pady=2)
    app.s1_S=InpRow(c,"行程 S","mm","","有效工作行程");app.s1_S.pack(fill="x",pady=2)
    app.s1_f=InpRow(c,"工作频率 f","次/min",1,"每分钟循环次数");app.s1_f.pack(fill="x",pady=2)

    c2=Card(p,"环境温度条件");c2.pack(fill="x",padx=10,pady=4)
    app.s1_Te=InpRow(c2,"环境温度 T_env","℃",30);app.s1_Te.pack(fill="x",pady=2)
    app.s1_Tm=InpRow(c2,"允许最高油温 T_max","℃",60,"≤65正常|短期≤75");app.s1_Tm.pack(fill="x",pady=2)

    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 计算工况分析",safe(c1,app),C_ACCENT).pack()

    c3=Card(p,"工况分析结果");c3.pack(fill="x",padx=10,pady=4)
    app.r1_P=Res(c3,"峰值功率(负载×速度)","kW",C_ORANGE);app.r1_P.pack(fill="x",pady=1)
    app.r1_lp=Res(c3,"负载率(是否需蓄能器)","");app.r1_lp.pack(fill="x",pady=1)
    app.r1_al=tk.Frame(c3,bg=C_PANEL);app.r1_al.pack(fill="x",padx=4,pady=2)
    app.r1_al_lb=tk.Text(app.r1_al,bg=C_PANEL,font=F(10),height=1,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r1_al_lb.pack(fill="x");app.r1_al_lb.insert("1.0","")

def _set_v(app):
    for p in app.s1_vp.get().split():
        try: app.s1_v.set(float(p),3);return
        except: continue

def c1(app):
    app._collect()
    F=app.s1_F.get_valid_f("负载F",0);v=app.s1_v.get_valid_f("速度v",0)
    if F[0]is None or v[0]is None:
        if F[0]is None: app.s1_F.warn(True)
        if v[0]is None: app.s1_v.warn(True)
        app.msg("请填写F_max和v_max");return
    app.s1_F.warn(False);app.s1_v.warn(False)
    F,v=F[0],v[0];S=app.s1_S.getf(0);f=app.s1_f.getf(1);Te=app.s1_Te.getf(30);Tm=app.s1_Tm.getf(60)
    Pp=F*v/1000
    if v>0 and S>0:
        duty=min(S/1000/v/(60/max(f,0.1))*2,1.0)
        lp=1.0+(1-duty)*0.5
    else: lp=1.0
    app.data["F_N"]=F;app.data["v_max"]=v;app.data["S_mm"]=S;app.data["f_cycle"]=f
    app.data["T_env"]=Te;app.data["T_max"]=Tm
    app.data["P_peak_kW"]=Pp;app.data["lambda_p"]=lp;app.data["F_kgf"]=F/9.80665;app.data["F_ton"]=F/9806.65
    app.r1_P.set(Pp,3);app.r1_lp.set(lp,2)
    col,text=(C_GREEN,f"✓ 平稳 λ_p={lp:.2f}") if lp<=1.2 else (
        (C_YELLOW,f"△ 中等 λ_p={lp:.2f} 建议蓄能器") if lp<=1.5 else (C_RED,f"✗ 剧烈 λ_p={lp:.2f} ★推荐蓄能器"))
    app.r1_al_lb.delete("1.0","end");app.r1_al_lb.insert("1.0",text);app.r1_al_lb.config(fg=col)
    app.msg(f"完成 | F={F:.0f}N P_peak={Pp:.3f}kW")

# ==================== 步骤2 ====================
def b2(p,app):
    step_title(p,"步骤 2：系统压力等级与阀门通径匹配","Pressure & Valve Selection")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="6.3MPa(农机)|10MPa(一般)|★16MPa最常用|25MPa(挖掘)|31.5MPa(矿山)|40MPa(特殊)",bg=C_BG,fg=C_TEXT2,font=F(9),wraplength=1300).pack(anchor="w")

    c=Card(p,"压力等级与阀门参数");c.pack(fill="x",padx=10,pady=4)
    pr=tk.Frame(c,bg=C_PANEL);pr.pack(fill="x",pady=2)
    tk.Label(pr,text="系统公称压力 p_sys",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.pv=tk.StringVar(value="16")
    ttk.Combobox(pr,textvariable=app.pv,values=[str(x)for x in STD_PRESSURE],state="readonly",font=F(),width=10).pack(side="left",padx=4)
    tk.Label(pr,text="MPa",bg=C_PANEL,fg=C_TEXT2,font=F()).pack(side="left",padx=2)
    app.pv_lb=tk.Label(pr,text=PRESSURE_INFO[16],bg=C_PANEL,fg=C_ACCENT,font=F(9))
    app.pv_lb.pack(side="left",padx=10,fill="x")
    def _pv(*a):
        try: app.pv_lb.config(text=PRESSURE_INFO.get(float(app.pv.get()),""))
        except: pass
    app.pv.trace_add("write",_pv)
    app.s2_eta=InpRow(c,"机械效率 ηₘ","",0.92,"新0.85|中0.90|老0.95");app.s2_eta.pack(fill="x",pady=2)
    vf=tk.Frame(c,bg=C_PANEL);vf.pack(fill="x",pady=2)
    tk.Label(vf,text="阀门通径规格",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.vv=ttk.Combobox(vf,values=list(VALVE_DATA.keys()),state="readonly",font=F(),width=30)
    app.vv.pack(side="left",padx=4)
    app.vv_lb=tk.Label(vf,text="请选择阀门规格",bg=C_PANEL,fg=C_ACCENT,font=F(9))
    app.vv_lb.pack(side="left",padx=6)
    app.vv.bind("<<ComboboxSelected>>",lambda e:app.vv_lb.config(text=VALVE_DATA.get(app.vv.get(),{}).get("desc","")))

    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 计算压力与阀门匹配",safe(c2,app)).pack()

    c2r=Card(p,"压力-阀门匹配结果");c2r.pack(fill="x",padx=10,pady=4)
    app.r2_p=Res(c2r,"选定系统压力","MPa",C_ACCENT);app.r2_p.pack(fill="x",pady=1)
    app.r2_Dc=Res(c2r,"理论缸径(按压力)","mm",C_ORANGE);app.r2_Dc.pack(fill="x",pady=1)
    app.r2_Qe=Res(c2r,"预估流量(压力管)","L/min");app.r2_Qe.pack(fill="x",pady=1)
    app.r2_dp=Res(c2r,"★推荐压力管通径(4~6m/s)","mm");app.r2_dp.pack(fill="x",pady=1)
    app.r2_dp_s=Res(c2r,"推荐吸油管通径(0.5~1.5m/s)","mm");app.r2_dp_s.pack(fill="x",pady=1)
    app.r2_dp_r=Res(c2r,"推荐回油管通径(1.5~3m/s)","mm");app.r2_dp_r.pack(fill="x",pady=1)
    app.r2_vc_lb=tk.Text(c2r,bg=C_PANEL,font=F(9),height=1,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r2_vc_lb.pack(fill="x",padx=4)

def c2(app):
    app._collect()
    F=app._gk("F_N",0)
    if F<=0: app.msg("请先完成步骤1");return
    try: ps=float(app.pv.get())
    except: ps=16
    eta=app.s2_eta.getf(0.92)
    if eta<=0: eta=0.92
    app.data["p_sys"]=ps;app.data["eta_m"]=eta
    Dc=bore_by_force(F,ps,eta)
    v=app._gk("v_max",0)
    Qe=flow_rate(piston_area_m2(Dc),v)
    app.r2_p.set(ps,1);app.r2_Dc.set(f"{Dc:.1f}" if Dc>0 else "--");app.r2_Qe.set(f"{Qe:.1f}" if Qe>0 else "--")
    v_press=4.0;v_suck=1.0;v_ret=2.0  # 压力/吸油/回油 推荐流速
    dp=math.sqrt(4*Qe/1000/60/math.pi/v_press)*1000 if Qe>0 else 0
    d_suck=math.sqrt(4*Qe/1000/60/math.pi/v_suck)*1000 if Qe>0 else 0
    d_ret=math.sqrt(4*Qe/1000/60/math.pi/v_ret)*1000 if Qe>0 else 0
    app.r2_dp.set(f"{dp:.0f}" if dp>0 else "--");app.data["d_pipe"]=dp
    app.r2_dp_s.set(f"{d_suck:.0f}" if d_suck>0 else "--")
    app.r2_dp_r.set(f"{d_ret:.0f}" if d_ret>0 else "--")
    Qv=app._gk("Q_valve_max",0)
    if Qv>0:
        r=Qe/Qv
        if r<=0.85: col,txt=C_GREEN,f"✓ 需求{Qe:.1f}≤阀{Qv}(余量{(1-r)*100:.0f}%)"
        elif r<=1: col,txt=C_YELLOW,f"△ 需求{Qe:.1f}接近阀{Qv}"
        else: col,txt=C_RED,f"✗ 需求{Qe:.1f}>阀{Qv}"
        app.r2_vc_lb.delete("1.0","end");app.r2_vc_lb.insert("1.0",txt);app.r2_vc_lb.config(fg=col)
    app.msg(f"完成 | p={ps}MPa")

# ==================== 步骤2a ====================
def b2a(p,app):
    step_title(p,"步骤 2a：蓄能器选型（可选）","Accumulator Sizing")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="峰值补偿·紧急动力·吸收脉动·保压补偿",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")

    c=Card(p,"蓄能器配置");c.pack(fill="x",padx=10,pady=4)
    app.acc_use=tk.StringVar(value="no")
    r1=tk.Frame(c,bg=C_PANEL);r1.pack(fill="x",pady=2)
    tk.Radiobutton(r1,text="不选用",variable=app.acc_use,value="no",selectcolor=C_PANEL,font=F(),command=lambda:_at(app)).pack(side="left",padx=4)
    tk.Radiobutton(r1,text="使用蓄能器",variable=app.acc_use,value="yes",selectcolor=C_PANEL,font=F(),command=lambda:_at(app)).pack(side="left",padx=4)

    app.atf=tk.Frame(c,bg=C_PANEL)
    tk.Label(app.atf,text="蓄能器类型",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.acc_tv=ttk.Combobox(app.atf,values=ACC_TYPES[1:],state="readonly",font=F(),width=40);app.acc_tv.pack(side="left",padx=4)

    app.acc_Vr=InpRow(c,"补偿油量 ΔV","L","","峰值时需要的额外油量")
    app.acc_p1=InpRow(c,"最低工作压力 p₁","MPa","","蓄能器开始供油时的压力")
    app.acc_p2=InpRow(c,"最高工作压力 p₂","MPa","","蓄能器充油结束时的压力")

    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 蓄能器计算",safe(c2a,app)).pack()

    c2r=Card(p,"蓄能器计算结果");c2r.pack(fill="x",padx=10,pady=4)
    app.r2a_V0=Res(c2r,"公称容积 V₀","L",C_ACCENT);app.r2a_V0.pack(fill="x",pady=1)
    app.r2a_nt=Res(c2r,"状态","");app.r2a_nt.pack(fill="x",pady=1)
    app.r2a_al=tk.Frame(c2r,bg=C_PANEL);app.r2a_al.pack(fill="x",padx=4,pady=2)
    app.r2a_al_lb=tk.Text(app.r2a_al,bg=C_PANEL,font=F(10),height=1,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r2a_al_lb.pack(fill="x")
    _at(app)

def _at(app):
    if app.acc_use.get()=="yes":
        app.atf.pack(fill="x",pady=2);app.acc_Vr.pack(fill="x",pady=2)
        app.acc_p1.pack(fill="x",pady=2);app.acc_p2.pack(fill="x",pady=2)
    else:
        app.atf.pack_forget();app.acc_Vr.pack_forget();app.acc_p1.pack_forget();app.acc_p2.pack_forget()
        app.r2a_V0.set("—(未使用)");app.r2a_al_lb.delete("1.0","end")

def c2a(app):
    app._collect()
    lp=app._gk("lambda_p",1.0)
    if app.acc_use.get()=="no":
        app.r2a_V0.set("—(未使用)")
        if lp>1.5:
            app.r2a_al_lb.delete("1.0","end");app.r2a_al_lb.insert("1.0","⛔ 负载波动剧烈，强烈建议使用蓄能器");app.r2a_al_lb.config(fg=C_RED)
        elif lp>1.2:
            app.r2a_al_lb.delete("1.0","end");app.r2a_al_lb.insert("1.0","△ 负载中等波动，建议考虑使用蓄能器");app.r2a_al_lb.config(fg=C_YELLOW)
        else:
            app.r2a_al_lb.delete("1.0","end");app.r2a_al_lb.insert("1.0","✓ 负载平稳，无需蓄能器");app.r2a_al_lb.config(fg=C_GREEN)
        app.r2a_nt.set("—(未使用)");app.data["use_acc"]="no";return
    dV=app.acc_Vr.getf(0);p1=app.acc_p1.getf(0);p2=app.acc_p2.getf(0)
    if dV<=0 or p1<=0 or p2<=p1:
        app.r2a_al_lb.delete("1.0","end");app.r2a_al_lb.insert("1.0","⛔ 请完整填写：补偿油量ΔV、最低压力p₁、最高压力p₂（p₂必须大于p₁）");app.r2a_al_lb.config(fg=C_RED);return
    # 修正: 使用标准等温气体定律公式 V0 = ΔV / (p0/p1 - p0/p2)
    # 压力转换为绝对压力(bar), 充气压力 p0 = 0.9 × p1
    # 参考: 《现代液压气动手册》2024 第32章
    V0_iso = accumulator_V0_isothermal(dV, p1, p2)
    V0_adi = accumulator_V0_adiabatic(dV, p1, p2)
    V0 = V0_iso  # 默认等温(充放油速度较慢)
    # 快速响应工况提示绝热结果
    adiabatic_note = f" (快速响应绝热工况建议 V₀≥{V0_adi:.1f}L)" if abs(V0_adi-V0_iso)/max(V0_iso,0.1)>0.15 else ""
    app.data.update({"use_acc":"yes","acc_type":app.acc_tv.get(),"acc_Vr":dV,"acc_V0":V0,
                     "acc_V0_adi":V0_adi})
    app.r2a_nt.set("已配置 (等温公式)")
    app.r2a_al_lb.delete("1.0","end");app.r2a_al_lb.insert("1.0",f"✓ 已配置 V₀={V0:.1f}L (等温公式){adiabatic_note}");app.r2a_al_lb.config(fg=C_GREEN)
    if V0>0 and V0<dV:
        app.r2a_al_lb.insert("end",f"\n⚠ 公称容积V₀({V0:.1f}L)小于补偿油量ΔV({dV:.1f}L)，请确认参数是否合理")

# ==================== 步骤3 ====================
def b3(p,app):
    step_title(p,"步骤 3：缸径计算与标准化","Bore Diameter & GB/T 2348")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="标准缸径 GB/T 2348: 25 32 40 50 63 80 | 90 100 110 125 | 140 160 180 200 220 250 | 280 320 360 400",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")

    c=Card(p,"缸径设置");c.pack(fill="x",padx=10,pady=4)
    mf=tk.Frame(c,bg=C_PANEL);mf.pack(fill="x",pady=2)
    app.s3_m=tk.StringVar(value="auto")
    tk.Radiobutton(mf,text="系统推荐",variable=app.s3_m,value="auto",selectcolor=C_PANEL,font=F(),command=lambda:_dt3(app)).pack(side="left",padx=4)
    tk.Radiobutton(mf,text="自定义",variable=app.s3_m,value="custom",selectcolor=C_PANEL,font=F(),command=lambda:_dt3(app)).pack(side="left",padx=4)
    app.s3_cf=tk.Frame(c,bg=C_PANEL)
    app.s3_cD=InpRow(app.s3_cf,"自定义缸径 D","mm","");app.s3_cD.pack()
    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 缸径计算",safe(c3,app)).pack(side="left",padx=4)

    c3r=Card(p,"缸径计算结果");c3r.pack(fill="x",padx=10,pady=4)
    app.r3_Dc=Res(c3r,"理论缸径(按负载/压力)","mm",C_ACCENT);app.r3_Dc.pack(fill="x",pady=1)
    app.r3_Ds=Res(c3r,"选定标准缸径","mm",C_ORANGE);app.r3_Ds.pack(fill="x",pady=1)
    app.r3_A=Res(c3r,"活塞面积","mm²",C_GREEN);app.r3_A.pack(fill="x",pady=1)
    app.r3_pa=Res(c3r,"实际工作压力","MPa");app.r3_pa.pack(fill="x",pady=1)
    app.r3_Fa=Res(c3r,"实际推力","kN",C_GREEN);app.r3_Fa.pack(fill="x",pady=1)
    app.r3_al=tk.Frame(c3r,bg=C_PANEL);app.r3_al.pack(fill="x",padx=4,pady=2)
    app.r3_al_lb=tk.Text(app.r3_al,bg=C_PANEL,font=F(9),height=1,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r3_al_lb.pack(fill="x")

def _dt3(app):
    if app.s3_m.get()=="custom": app.s3_cf.pack(fill="x",pady=2)
    else: app.s3_cf.pack_forget()

def c3(app):
    app._collect()
    F=app._gk("F_N",0);ps=app._gk("p_sys",16)
    if F<=0: app.msg("请先完成步骤1");return
    eta=app._gk("eta_m",0.92)
    if eta<=0: eta=0.92
    Dc=bore_by_force(F,ps,eta);app.data["D_calc"]=Dc;app.r3_Dc.set(Dc,1)
    if app.s3_m.get()=="custom":
        Ds=app.s3_cD.getf(0)
        if Ds<=0: app.msg("请填写自定义缸径");return
        delta=(Ds/Dc-1)*100
        if Ds not in STD_BORE:
            app.r3_al_lb.delete("1.0","end");app.r3_al_lb.insert("1.0",f"△ 您输入{Ds}mm不在标准缸径系列(GB/T 2348)中，密封件需定制");app.r3_al_lb.config(fg=C_ORANGE)
        elif abs(delta)<=15:
            app.r3_al_lb.delete("1.0","end");app.r3_al_lb.insert("1.0",f"✓ 自定义缸径{pretty_delta(delta)}，偏差在合理范围内");app.r3_al_lb.config(fg=C_GREEN)
        elif delta>15:
            app.r3_al_lb.delete("1.0","end");app.r3_al_lb.insert("1.0",f"⚠ 您选的{Ds}mm{pretty_delta(delta)}，推力偏大浪费成本，建议{nearest(Ds,STD_BORE)}mm");app.r3_al_lb.config(fg=C_YELLOW)
        else:
            app.r3_al_lb.delete("1.0","end");app.r3_al_lb.insert("1.0",f"✗ 您选的{Ds}mm{pretty_delta(delta)}，推力不足，建议{nearest(Ds,STD_BORE)}mm");app.r3_al_lb.config(fg=C_RED)
    else: Ds=nearest(Dc,STD_BORE)
    app.data["D_std"]=Ds;app.r3_Ds.set(Ds,0)
    A=piston_area_m2(Ds);app.data["A_piston_mm2"]=A*1e6;app.r3_A.set(A*1e6,0)
    pa=F/A/1e6/eta;app.data["p_actual"]=pa;app.r3_pa.set(pa,2)
    Fp=A*ps*1e6*eta/1000;app.data["F_push"]=Fp;app.r3_Fa.set(Fp,1)
    app.r3_al_lb.delete("1.0","end");app.r3_al_lb.insert("1.0",f"{'✓' if pa<=ps*1.1 else '⚠'} 实际工作压力{pa:.2f}MPa，{'在' if pa<=ps*1.1 else '超过'}系统压力{ps}MPa的1.1倍范围内，{'设计合理' if pa<=ps*1.1 else '建议升高一级压力等级'}");app.r3_al_lb.config(fg=C_GREEN if pa<=ps*1.1 else C_YELLOW)
    app.msg(f"完成 | D={Ds:.0f}mm")

# ==================== 步骤4 ====================
def b4(p,app):
    step_title(p,"步骤 4：活塞杆直径与速比","Rod Diameter & Speed Ratio")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="p≤5MPa→d/D≈0.35 | 5-7→0.5 | >7→0.7",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")
    c=Card(p,"杆径设置");c.pack(fill="x",padx=10,pady=4)
    mf=tk.Frame(c,bg=C_PANEL);mf.pack(fill="x",pady=2)
    app.s4_m=tk.StringVar(value="auto")
    tk.Radiobutton(mf,text="系统推荐",variable=app.s4_m,value="auto",selectcolor=C_PANEL,font=F(),command=lambda:_dt4(app)).pack(side="left",padx=4)
    tk.Radiobutton(mf,text="自定义",variable=app.s4_m,value="custom",selectcolor=C_PANEL,font=F(),command=lambda:_dt4(app)).pack(side="left",padx=4)
    app.s4_cf=tk.Frame(c,bg=C_PANEL)
    app.s4_cd=InpRow(app.s4_cf,"自定义杆径 d","mm","");app.s4_cd.pack()
    app.s4_Fpr=InpRow(c,"所需拉力 F_pull(有回程负载)","N",0,"推力系统填0");app.s4_Fpr.pack(fill="x",pady=2)
    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 杆径与速比",safe(c4,app)).pack()
    c4r=Card(p,"杆径与速比结果");c4r.pack(fill="x",padx=10,pady=4)
    app.r4_ra=Res(c4r,"推荐d/D比值","");app.r4_ra.pack(fill="x",pady=1)
    app.r4_ds=Res(c4r,"选定杆径","mm",C_ACCENT);app.r4_ds.pack(fill="x",pady=1)
    app.r4_Fp=Res(c4r,"实际推力(无杆腔)","kN",C_GREEN);app.r4_Fp.pack(fill="x",pady=1)
    app.r4_Fpl=Res(c4r,"实际拉力(有杆腔)","kN",C_ACCENT2);app.r4_Fpl.pack(fill="x",pady=1)
    app.r4_ph=Res(c4r,"速比","");app.r4_ph.pack(fill="x",pady=1)
    app.r4_al=tk.Frame(c4r,bg=C_PANEL);app.r4_al.pack(fill="x",padx=4,pady=2)
    app.r4_al_lb=tk.Text(app.r4_al,bg=C_PANEL,font=F(9),height=1,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r4_al_lb.pack(fill="x")

def _dt4(app):
    if app.s4_m.get()=="custom": app.s4_cf.pack(fill="x",pady=2)
    else: app.s4_cf.pack_forget()

def c4(app):
    app._collect()
    Ds=app._gk("D_std",0);pa=app._gk("p_actual",16)
    if Ds<=0: app.msg("请先完成步骤3");return
    eta=app._gk("eta_m",0.92)
    dr=0.35 if pa<=5 else 0.5 if pa<=7 else 0.7
    app.r4_ra.set(f"d/D={dr:.2f}")
    Frq=app.s4_Fpr.getf(0)
    if app.s4_m.get()=="custom":
        ds=app.s4_cd.getf(0)
        if ds<=0 or ds>=Ds: app.msg(f"杆径需在0~{Ds}");return
    else:
        ds=nearest(Ds*dr,STD_ROD)
        while ds>=Ds*0.95:
            cand=[r for r in STD_ROD if r<Ds*0.95]
            ds=nearest(Ds*dr,cand) if cand else Ds*0.85
    app.data["d_std"]=ds;app.r4_ds.set(ds,0)
    Ap=piston_area_m2(Ds);Ar=annulus_area_m2(Ds,ds)
    ps=app._gk("p_sys",16)
    Fp=Ap*ps*1e6*eta/1000;Fpl=Ar*ps*1e6*eta/1000;phi=Ap/Ar if Ar>0 else 1
    app.data.update({"F_push":Fp,"F_pull":Fpl,"phi":phi})
    app.r4_Fp.set(Fp,1);app.r4_Fpl.set(Fpl,1);app.r4_ph.set(phi,2)
    dd=ds/Ds
    if abs(dd-dr)<=0.1: col,txt=C_GREEN,f"✓ d/D={dd:.2f}"
    elif dd<dr: col,txt=C_YELLOW,f"⚠ 偏细≥{Ds*dr:.0f}"
    else: col,txt=C_ORANGE,f"△ 偏粗≤{Ds*dr:.0f}"
    if Frq>0 and Fpl*1000<Frq: txt+=" ⚠拉力不足";col=C_RED
    app.r4_al_lb.delete("1.0","end");app.r4_al_lb.insert("1.0",txt);app.r4_al_lb.config(fg=col)
    app.msg(f"完成 | d={ds:.0f}mm")

# ==================== 步骤5 ====================
def b5(p,app):
    step_title(p,"步骤 5：缸筒壁厚与材料强度","Wall Thickness & Material Strength")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="薄壁δ≤0.08D: δ≥pD/2[σ] | 厚壁:第四强度理论",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")
    c=Card(p,"材料与计算参数");c.pack(fill="x",padx=10,pady=4)
    mf=tk.Frame(c,bg=C_PANEL);mf.pack(fill="x",pady=2)
    tk.Label(mf,text="缸筒材料",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.s5_m=ttk.Combobox(mf,values=list(STEEL_DB.keys()),state="readonly",font=F(),width=12)
    app.s5_m.pack(side="left",padx=4);app.s5_m.set("45#")
    app.s5_mi=tk.Label(mf,text="",bg=C_PANEL,fg=C_ACCENT,font=F(9))
    app.s5_mi.pack(side="left",padx=10,fill="x")
    def _ms(*a):
        m=app.s5_m.get()
        if m in STEEL_DB: app.s5_mi.config(text=STEEL_DB[m]["desc"])
    app.s5_m.bind("<<ComboboxSelected>>",_ms);_ms(None)
    app.s5_n=InpRow(c,"安全系数 n","",4,"N<10⁴→3.5|10⁴-10⁶→4|>10⁶→5");app.s5_n.pack(fill="x",pady=2)
    app.s5_pm=InpRow(c,"最大冲击压力 p_max","MPa","","系统安全阀压力×1.25");app.s5_pm.pack(fill="x",pady=2)
    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 壁厚强度计算",safe(c5,app)).pack()
    c5r=Card(p,"壁厚与强度结果");c5r.pack(fill="x",padx=10,pady=4)
    app.r5_m=Res(c5r,"屈服σs/许用[σ]","MPa",C_RED);app.r5_m.pack(fill="x",pady=1)
    app.r5_pm=Res(c5r,"最大压力p_max","MPa");app.r5_pm.pack(fill="x",pady=1)
    app.r5_tc=Res(c5r,"计算壁厚δ","mm",C_ORANGE);app.r5_tc.pack(fill="x",pady=1)
    app.r5_wc=Res(c5r,"选定标准壁厚","mm",C_GREEN);app.r5_wc.pack(fill="x",pady=1)
    app.r5_Do=Res(c5r,"缸筒外径(D+2δ)","mm");app.r5_Do.pack(fill="x",pady=1)

def c5(app):
    app._collect()
    Ds=app._gk("D_std",0);ps=app._gk("p_sys",16)
    if Ds<=0: app.msg("请先完成步骤3");return
    mat=app.s5_m.get()
    if mat not in STEEL_DB: app.msg("选材料");return
    n=app.s5_n.getf(4);pm=app.s5_pm.getf(ps*1.25)
    if pm<=0: pm=ps*1.25
    st=STEEL_DB[mat];ss=st["σs"];sg=ss/n
    app.data.update({"material":mat,"sigma_s":ss,"n_safety":n})
    app.r5_m.set(f"{ss}/[{sg:.1f}]");app.r5_pm.set(pm,1)
    # 修正: 使用 wall_thickness() 函数，以实际 δ/D 比值判断薄壁/厚壁
    wall, wt_formula, wt_ratio = wall_thickness(Ds, pm, ss, n)
    ws=nearest(wall,STD_WALL);Do=Ds+2*ws
    app.data.update({"wall_calc":wall,"wall_std":ws,"D_out":Do,"wall_formula":wt_formula})
    app.r5_tc.set(wall,1);app.r5_wc.set(ws,1);app.r5_Do.set(Do,0)
    app.msg(f"完成 | {mat} δ={wall:.1f}mm D_out={Do:.0f}mm")

# ==================== 步骤6 ====================
def b6(p,app):
    step_title(p,"步骤 6：活塞杆稳定性校核","Buckling Analysis")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="两端铰支μ=1.0 | 一端固一端自由2.0 | 两端固定0.5 | 一端固一端铰0.7",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")
    c=Card(p,"安装方式与边界条件");c.pack(fill="x",padx=10,pady=4)
    mf=tk.Frame(c,bg=C_PANEL);mf.pack(fill="x",pady=2)
    tk.Label(mf,text="安装方式",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    mo=["两端铰支(耳环)  μ=1.0 ★常见","一端固一端自由(举升)  μ=2.0","两端固定(法兰)  μ=0.5","一端固一端铰  μ=0.7"]
    app.s6_mt_cb=ttk.Combobox(mf,values=mo,state="readonly",font=F(),width=30)
    app.s6_mt_cb.pack(side="left",padx=4);app.s6_mt_cb.set(mo[0])
    app.s6_mi=tk.Label(mf,text="",bg=C_PANEL,fg=C_ACCENT,font=F(8))
    app.s6_mi.pack(side="left",padx=6,fill="x")
    app.s6_mt_cb.bind("<<ComboboxSelected>>",lambda e:_mc(app))
    app.s6_mu=InpRow(c,"安装长度系数 μ(自动)",1.0,1.0);app.s6_mu.pack(fill="x",pady=2)
    app.s6_ma=InpRow(c,"安装余量(L=S+余量)","mm",200,"耳环150-300|法兰50-100");app.s6_ma.pack(fill="x",pady=2)
    app.s6_nr=InpRow(c,"许用稳定安全系数[n_st]","",10,"推荐8-10");app.s6_nr.pack(fill="x",pady=2)
    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 稳定性校核",safe(c6,app)).pack()
    c6r=Card(p,"稳定性校核结果");c6r.pack(fill="x",padx=10,pady=4)
    app.r6_L=Res(c6r,"压杆总长L=S+余量","mm");app.r6_L.pack(fill="x",pady=1)
    app.r6_la=Res(c6r,"柔度λ","",C_ORANGE);app.r6_la.pack(fill="x",pady=1)
    app.r6_tp=Res(c6r,"压杆分类","");app.r6_tp.pack(fill="x",pady=1)
    app.r6_Pc=Res(c6r,"临界失稳载荷","kN",C_ACCENT2);app.r6_Pc.pack(fill="x",pady=1)
    app.r6_ns=Res(c6r,"稳定安全系数n_st","");app.r6_ns.pack(fill="x",pady=1)
    app.r6_ad=Res(c6r,"判定","");app.r6_ad.pack(fill="x",pady=1)
    app.r6_al=tk.Frame(c6r,bg=C_PANEL);app.r6_al.pack(fill="x",padx=4,pady=2)
    app.r6_al_lb=tk.Text(app.r6_al,bg=C_PANEL,font=F(9),height=3,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r6_al_lb.pack(fill="x")
    app.r6_al_lb.pack(fill="x")
    _mc(app)

def _mc(app):
    txt=app.s6_mt_cb.get()
    if "μ=2.0" in txt: app.s6_mu.set(2.0,1);app.s6_mi.config(text="一端固定一端自由，最不利!")
    elif "μ=0.5" in txt: app.s6_mu.set(0.5,1);app.s6_mi.config(text="两端法兰固定，最有利!")
    elif "μ=0.7" in txt: app.s6_mu.set(0.7,1);app.s6_mi.config(text="一端固定一端铰支")
    else: app.s6_mu.set(1.0,1);app.s6_mi.config(text="两端铰支，最常见")

def c6(app):
    app._collect()
    Ds=app._gk("D_std",0);ds=app._gk("d_std",0);S=app._gk("S_mm",0);F=app._gk("F_N",0)
    if Ds<=0 or ds<=0 or S<=0: app.msg("请先完成1和4");return
    mat=app._gk("material","45#")
    if mat not in STEEL_DB: mat="45#"
    mu=app.s6_mu.getf(1.0);mt=app.s6_ma.getf(200);nr=app.s6_nr.getf(10)
    st=STEEL_DB[mat];L=S+mt
    # 统一使用 mm 单位体系:
    # E 在 STEEL_DB 中为 MPa (= N/mm²), ds 转换为 mm, L 已是 mm
    ds_mm = ds  # ds 本来就是 mm
    I_mm4 = math.pi * ds_mm**4 / 64
    Ar_mm2 = math.pi * ds_mm**2 / 4
    i_mm = math.sqrt(I_mm4 / Ar_mm2) if Ar_mm2 > 0 else 0
    Le_mm = mu * L
    lam = Le_mm / i_mm if i_mm > 0 else 0
    sp = st.get("σp", 300)
    l1 = math.pi * math.sqrt(st["E"] / sp) if sp > 0 else 100
    l2 = (st["a"] - sp) / st["b"] if st["b"] > 0 else 60
    if lam >= l1:
        Pcr = math.pi**2 * st["E"] * I_mm4 / Le_mm**2 / 1000
        tp = f"大柔度λ≥{l1:.0f}→欧拉"
    elif lam >= l2:
        sc = st["a"] - st["b"] * lam
        Pcr = sc * Ar_mm2 / 1000
        tp = f"中柔度{l2:.0f}≤λ<{l1:.0f}"
    else:
        Pcr = st["σs"] * Ar_mm2 / 1000
        tp = f"小柔度λ<{l2:.0f}→屈服"
    nse=Pcr/(F/1000) if F>0 else 0
    # 注意: 柔度 λ 已经通过 Euler/Tetmajer 公式完整捕捉了长细比效应
    # 不再叠加非标准的 L/d 惩罚因子
    passed=nse>=nr
    app.data.update({"L_rod":L,"lam":lam,"Pcr":Pcr,"n_st":nse,"buckle_pass":passed})
    app.r6_L.set(L,0);app.r6_la.set(lam,1);app.r6_tp.set(tp);app.r6_Pc.set(Pcr,1);app.r6_ns.set(nse,2)
    if nse>=nr:
        col,bg=C_GREEN,"#f0fdf4"
        ad=f"✓ 稳定安全系数 n_st={nse:.2f} ≥ 许用值[{nr}] → 设计安全，活塞杆不会失稳弯曲"
        txt=ad
    elif nse>=nr*0.7:
        col,bg=C_YELLOW,"#fff3cd"
        need_d=ds*math.sqrt(nr/max(nse,0.01))
        ad=f"⚠ 临界状态 n_st={nse:.2f} < 许用值[{nr}]"
        txt=f"⚠ n_st={nse:.2f} < [{nr}]，安全余量不足。建议将活塞杆直径增大至约{need_d:.0f}mm，或减小安装行程"
    else:
        col,bg=C_RED,"#fde8e8"
        # need_d 基于稳定性需求反推: n_st_req = Pcr_new / (F/1000)
        # 假设增大杆径后仍落在此 regime，用 yield 公式估算: n_st ∝ d²→d⁴
        need_d=((nr/max(nse,0.01))*ds_mm**4)**0.25
        if need_d<Ds*0.95:
            txt=f"✗ 不通过！n_st={nse:.2f} << [{nr}]，失稳风险高。建议方案：\n①增大杆径至≥{need_d:.0f}mm\n②加中间支撑套缩短有效压杆长度\n③改用两端固定安装(μ=0.5)"
        else:
            txt=f"✗ 不通过！n_st={nse:.2f} << [{nr}]，失稳风险高。建议方案：\n①加中间支撑套\n②改用两端固定安装(μ=0.5)\n③增大缸径D以增大杆径d"
        ad=f"✗ ★不通过★ n_st={nse:.2f} << [{nr}] 需加强"
    app.r6_ad.set(ad);app.r6_al_lb.delete("1.0","end");app.r6_al_lb.insert("1.0",txt);app.r6_al_lb.config(fg=col);app.r6_al.config(bg=bg)
    app.msg(f"完成 | λ={lam:.1f} n_st={nse:.2f}")

# ==================== 步骤7 ====================
def b7(p,app):
    step_title(p,"步骤 7：密封系统与缓冲","Seal System & Cushion")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="密封失效是液压缸第一故障模式！",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")
    c=Card(p,"密封与缓冲");c.pack(fill="x",padx=10,pady=4)
    sf=tk.Frame(c,bg=C_PANEL);sf.pack(fill="x",pady=2)
    tk.Label(sf,text="密封形式",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.s7_s=ttk.Combobox(sf,values=SEAL_TYPES,state="readonly",font=F(),width=52)
    app.s7_s.pack(side="left",padx=4);app.s7_s.set(SEAL_TYPES[0])
    bf=tk.Frame(c,bg=C_PANEL);bf.pack(fill="x",pady=2)
    tk.Label(bf,text="缓冲形式",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.s7_b=ttk.Combobox(bf,values=BUFFER_TYPES,state="readonly",font=F(),width=52)
    app.s7_b.pack(side="left",padx=4);app.s7_b.set(BUFFER_TYPES[0])
    app.s7_NAS=InpRow(c,"油液污染度 NAS等级","",9,"NAS7-8比例阀|NAS9工程机械");app.s7_NAS.pack(fill="x",pady=2)
    tk.Label(c,text="NAS每升1级→密封寿命缩短约25%",bg=C_PANEL,fg=C_TEXT2,font=F(8)).pack(fill="x",padx=4)

    bf2=tk.Frame(p,bg=C_BG);bf2.pack(fill="x",padx=10,pady=6)
    big_btn(bf2,"▶ 密封选型",safe(c7,app)).pack()
    c7r=Card(p,"密封与缓冲结果");c7r.pack(fill="x",padx=10,pady=4)
    app.r7_s=Res(c7r,"密封类型","");app.r7_s.pack(fill="x",pady=1)
    app.r7_eT=Res(c7r,"温度折扣","",C_ACCENT);app.r7_eT.pack(fill="x",pady=1)
    app.r7_ei=Res(c7r,"油污折扣","",C_ACCENT);app.r7_ei.pack(fill="x",pady=1)
    app.r7_lf=Res(c7r,"综合寿命","h",C_GREEN);app.r7_lf.pack(fill="x",pady=1)
    app.r7_b=Res(c7r,"缓冲形式","");app.r7_b.pack(fill="x",pady=1)

def c7(app):
    app._collect()
    Tm=app._gk("T_max",60);pa=app._gk("p_actual",16)
    etaT=0.12 if Tm>100 else 0.4 if Tm>85 else 0.6 if Tm>75 else 0.75 if Tm>65 else 1.0
    NAS=app.s7_NAS.getf(9)
    etai=max(0.1,1.0-max(NAS-5,0)*0.25) if NAS>=5 else 1.0
    base=2000 if pa>=31.5 else 2500 if pa>16 else 3000 if pa>10 else 3500
    life=base*etaT*etai
    app.data.update({"seal_type":app.s7_s.get(),"eta_T":etaT,"eta_iso":etai,"seal_life":life,"buffer_type":app.s7_b.get()})
    app.r7_s.set(app.s7_s.get());app.r7_eT.set(etaT,2);app.r7_ei.set(etai,2);app.r7_lf.set(life,0);app.r7_b.set(app.s7_b.get())
    app.msg(f"完成 | 寿命≈{life:.0f}h")

# ==================== 步骤8 ====================
def b8(p,app):
    step_title(p,"步骤 8：流量计算与泵阀匹配","Flow, Pump & Valve Matching")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="自动计算流量→推荐泵类型→管路压降校核",bg=C_BG,fg=C_TEXT2,font=F(9)).pack(anchor="w")
    c=Card(p,"泵源与电机参数");c.pack(fill="x",padx=10,pady=4)
    pf=tk.Frame(c,bg=C_PANEL);pf.pack(fill="x",pady=2)
    tk.Label(pf,text="液压泵类型",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.s8_pt=ttk.Combobox(pf,values=PUMP_TYPES,state="readonly",font=F(),width=48)
    app.s8_pt.pack(side="left",padx=4);app.s8_pt.set(PUMP_TYPES[0])
    ef=tk.Frame(c,bg=C_PANEL);ef.pack(fill="x",pady=2)
    tk.Label(ef,text="电机功率",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.s8_mo=ttk.Combobox(ef,values=["自动推荐"]+[f"{m}kW"for m in MOTOR_STD],state="readonly",font=F(),width=20)
    app.s8_mo.pack(side="left",padx=4);app.s8_mo.set("自动推荐")
    app.s8_n=InpRow(c,"泵转速 n_pump","rpm",1450);app.s8_n.pack(fill="x",pady=2)
    app.s8_ev=InpRow(c,"容积效率 ηv","",0.92);app.s8_ev.pack(fill="x",pady=2)
    app.s8_et=InpRow(c,"总效率 ηt","",0.85);app.s8_et.pack(fill="x",pady=2)
    app.s8_Lp=InpRow(c,"管路总长度","m",10);app.s8_Lp.pack(fill="x",pady=2)
    app.s8_zt=InpRow(c,"局部损失系数 ζ","",5);app.s8_zt.pack(fill="x",pady=2)
    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 流量泵阀计算",safe(c8,app)).pack()
    c8r=Card(p,"流量与泵阀结果");c8r.pack(fill="x",padx=10,pady=4)
    app.r8_Qf=Res(c8r,"前进流量","L/min");app.r8_Qf.pack(fill="x",pady=1)
    app.r8_Qr=Res(c8r,"回程流量","L/min");app.r8_Qr.pack(fill="x",pady=1)
    app.r8_Qd=Res(c8r,"★设计流量","L/min",C_RED);app.r8_Qd.pack(fill="x",pady=1)
    app.r8_Vg=Res(c8r,"泵排量","mL/r");app.r8_Vg.pack(fill="x",pady=1)
    app.r8_pr=Res(c8r,"★推荐泵","",C_GREEN);app.r8_pr.pack(fill="x",pady=1)
    app.r8_Pm=Res(c8r,"★电机功率","kW",C_GREEN);app.r8_Pm.pack(fill="x",pady=1)
    app.r8_vp=Res(c8r,"压力管流速","m/s");app.r8_vp.pack(fill="x",pady=1)
    app.r8_Re=Res(c8r,"雷诺数","");app.r8_Re.pack(fill="x",pady=1)
    app.r8_dp=Res(c8r,"管路总压降","bar",C_ORANGE);app.r8_dp.pack(fill="x",pady=1)
    app.r8_al=tk.Frame(c8r,bg=C_PANEL);app.r8_al.pack(fill="x",padx=4,pady=2)
    app.r8_al_lb=tk.Text(app.r8_al,bg=C_PANEL,font=F(10),height=1,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r8_al_lb.pack(fill="x")

def c8(app):
    app._collect()
    Ds=app._gk("D_std",0);ds=app._gk("d_std",0);v=app._gk("v_max",0);ps=app._gk("p_sys",16)
    if Ds<=0 or ds<=0: app.msg("请先完成3和4");return
    n=app.s8_n.getf(1450);ev=app.s8_ev.getf(0.92);et=app.s8_et.getf(0.85)
    Lp=app.s8_Lp.getf(10);zt=app.s8_zt.getf(5)
    A1=piston_area_m2(Ds);A2=annulus_area_m2(Ds,ds)
    Qf=flow_rate(A1,v);Qr=flow_rate(A2,v);Qd=max(Qf,Qr)
    Vg=Qd/n/ev*1000 if n*ev>0 else 0;Pm=ps*Qd/60/et if et>0 else 0
    app.data.update({"Q_fwd":Qf,"Q_ret":Qr,"Q_design":Qd,"Vg_pump":Vg,"P_motor":Pm})
    app.r8_Qf.set(Qf,1);app.r8_Qr.set(Qr,1);app.r8_Qd.set(Qd,1);app.r8_Vg.set(Vg,1)
    if Vg<=50: pr=f"齿轮泵 Vg={Vg:.1f}mL/r"
    elif Vg<=237: pr=f"叶片泵 Vg={Vg:.1f}mL/r"
    elif Vg<=500: pr=f"柱塞泵★ Vg={Vg:.1f}mL/r"
    else: pr=f"大排量柱塞/双泵 Vg={Vg:.1f}mL/r"
    app.data["pump_rec"]=pr;app.r8_pr.set(pr)
    Pi=min(MOTOR_STD,key=lambda x:abs(x-Pm*1.1))
    app.r8_Pm.set(f"{Pm:.2f}→{Pi}kW(4极)")
    dp=app._gk("d_pipe",10)/1000
    if dp>0 and Qd>0:
        Ap=math.pi*dp**2/4;vp=Qd/1000/60/Ap
        nu,rho=4.6e-5,870;Re=reynolds_number(vp,dp,nu)
        lf=friction_factor(Re);dpf=lf*(Lp/max(dp,0.001))*rho*vp**2/2/1e5
        dpl=zt*rho*vp**2/2/1e5;dpt=dpf+dpl;dlim=ps*0.08
        app.r8_vp.set(vp,2);app.r8_Re.set(f"{Re:.0f}");app.r8_dp.set(dpt,2)
        app.data.update({"Re":Re,"dp_total":dpt})
        if dpt<=dlim:
            col,txt=C_GREEN,f"✓ 管路压降校核通过！总压降Δp={dpt:.2f}bar(约{dpt*0.0145:.1f}psi)，在系统压力{ps}MPa的{dpt/ps*100:.1f}%以内，管径设计合理"
        else:
            col,txt=C_RED,f"✗ 管路压降超标！Δp={dpt:.2f}bar已超过系统压力{ps}MPa的8%(={dlim:.0f}bar)，需增大管径或缩短管路"
        app.r8_al_lb.delete("1.0","end");app.r8_al_lb.insert("1.0",txt);app.r8_al_lb.config(fg=col)
    app.msg(f"完成 | Qd={Qd:.1f}L/min")

# ==================== 步骤9 ====================
def b9(p,app):
    step_title(p,"步骤 9：热平衡与散热器","Heat Balance & Cooler")
    ep=tk.Frame(p,bg=C_BG);ep.pack(fill="x",padx=10,pady=2)
    tk.Label(ep,text="油温每升高10℃→密封寿命减半",bg=C_BG,fg=C_YELLOW,font=F(9,True)).pack(anchor="w")
    c=Card(p,"油箱与散热参数");c.pack(fill="x",padx=10,pady=4)
    app.s9_V=InpRow(c,"油箱容积 V_tank(可选)","L","");app.s9_V.pack(fill="x",pady=2)
    app.s9_k=InpRow(c,"油箱散热系数k","W/(m²·K)",15);app.s9_k.pack(fill="x",pady=2)
    app.s9_al=InpRow(c,"海拔修正系数","",1.0);app.s9_al.pack(fill="x",pady=2)
    cf=tk.Frame(c,bg=C_PANEL);cf.pack(fill="x",pady=2)
    tk.Label(cf,text="散热器类型",bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w").pack(side="left")
    app.s9_c=ttk.Combobox(cf,values=list(COOLER_TYPES.keys()),state="readonly",font=F(),width=20)
    app.s9_c.pack(side="left",padx=4);app.s9_c.set("风冷散热器")
    app.s9_ci=tk.Label(cf,text="",bg=C_PANEL,fg=C_ACCENT,font=F(9))
    app.s9_ci.pack(side="left",padx=6)
    def _sc(*a):
        ct=app.s9_c.get()
        if ct in COOLER_TYPES: app.s9_ci.config(text=f"系数{COOLER_TYPES[ct]}W/(m²·K)")
    app.s9_c.bind("<<ComboboxSelected>>",_sc);_sc(None)
    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=6)
    big_btn(bf,"▶ 热平衡计算",safe(c9,app)).pack()
    c9r=Card(p,"热平衡结果");c9r.pack(fill="x",padx=10,pady=4)
    app.r9_Pl=Res(c9r,"系统发热量","kW");app.r9_Pl.pack(fill="x",pady=1)
    app.r9_V=Res(c9r,"油箱容积","L");app.r9_V.pack(fill="x",pady=1)
    app.r9_Pt=Res(c9r,"自然散热能力","kW");app.r9_Pt.pack(fill="x",pady=1)
    app.r9_Te=Res(c9r,"平衡油温","℃",C_ORANGE);app.r9_Te.pack(fill="x",pady=1)
    app.r9_al=tk.Frame(c9r,bg=C_PANEL);app.r9_al.pack(fill="x",padx=2,pady=1)
    app.r9_al_lb=tk.Text(app.r9_al,bg=C_PANEL,font=F(10),height=1,wrap="word",relief="flat",bd=0,highlightthickness=0)
    app.r9_al_lb.pack(fill="x")
    c9r2=Card(p,"散热器选型");c9r2.pack(fill="x",padx=10,pady=4)
    app.r9_cr=Res(c9r2,"散热器面积A_cooler","m²",C_GREEN);app.r9_cr.pack(fill="x",pady=1)
    app.r9_cl=Res(c9r2,"推荐散热器","",C_ACCENT);app.r9_cl.pack(fill="x",pady=1)

def c9(app):
    app._collect()
    Pm=app._gk("P_motor",0);Qd=app._gk("Q_design",0);Te=app._gk("T_env",30);Tm=app._gk("T_max",60)
    if Pm<=0 or Qd<=0:
        if app._gk("F_N",0)<=0: app.msg("请先完成步骤1（填负载）再计算热平衡");return
        app.msg("请先完成步骤8（泵阀匹配）后再计算热平衡");return
    et=app.s8_et.getf(0.85)
    if et<=0: et=0.85
    Pl=Pm*(1-et);app.data["P_loss"]=Pl;app.r9_Pl.set(Pl,2)
    Vi=app.s9_V.getf(0)
    auto_v = False
    if Vi<=0: Vi=Qd*3; auto_v = True
    app.data["V_tank"]=Vi;app.r9_V.set(f"{Vi:.0f}" + (" (自动按3×Qₑ)" if auto_v else ""))
    Vm3=Vi/1000;Ae=2*(Vm3**(2/3))*6
    kc=app.s9_k.getf(15);al=app.s9_al.getf(1.0)
    Pt=Ae*kc*(Tm-Te)/1000*al;app.data["P_tank"]=Pt;app.r9_Pt.set(Pt,3)
    Teq=Te+Pl/Ae/kc*1000 if Ae*kc>0 else Te;app.data["T_eq"]=Teq;app.r9_Te.set(Teq,0)
    need=Pl>Pt*1.2;app.data["need_cooler"]=need
    app.r9_al_lb.delete("1.0","end");app.r9_al_lb.insert("1.0",f"{'⚠需要加装散热器!' if need else '✓自然冷却足够，无需散热器'} 系统发热量{Pl:.2f}kW，{'超过' if need else '未超过'}自然散热能力{Pt*1.2:.2f}kW，{'需配置散热器将油温控制在' if need else '油温可保持在'}{Tm}℃以内");app.r9_al_lb.config(fg=C_RED if need else C_GREEN)
    ct=app.s9_c.get();kc2=COOLER_TYPES.get(ct,25)
    if need:
        Ac=max(Pl-Pt,0.5)*1000/kc2/max(Tm-Te,5)
        app.data["A_cooler"]=Ac;app.data["cooler_type"]=ct
        app.r9_cr.set(Ac,1);app.r9_cl.set(f"{ct} ~{Ac:.1f}m²")
    else: app.r9_cr.set("—(无需)");app.r9_cl.set("✓自然冷却足够")
    app.msg(f"完成 | Pl={Pl:.2f}kW Teq={Teq:.0f}℃")

# ==================== 报告 ====================
def bR(p,app):
    step_title(p,"选型报告汇总","Final Selection Report")
    bf=tk.Frame(p,bg=C_BG);bf.pack(fill="x",padx=10,pady=4)
    big_btn(bf,"📋 生成报告",safe(gR,app),C_ACCENT).pack(side="left",padx=4)
    app.rt=tk.Text(p,bg=C_PANEL,fg=C_TEXT,font=("Consolas",10),wrap="word",relief="solid",padx=8,pady=6)
    app.rt.pack(fill="both",expand=True,padx=10,pady=6)

def gR(app):
    app._collect();app.rt.delete("1.0","end")
    w=lambda t:app.rt.insert("end",t+"\n");d=app.data
    w("="*76);w("  液压缸选型设计报告 V2.2");w(f"  生成时间: {datetime.now():%Y-%m-%d %H:%M}");w("="*76)
    w("\n【1】工况参数");w("─"*60)
    w(f"  · 最大负载力 F_max = {d.get('F_N',0):.0f} N  =  {d.get('F_kgf',0):.1f} kgf  =  {d.get('F_ton',0):.2f} 吨")
    w(f"  · 最高运动速度 v_max = {d.get('v_max',0):.3f} m/s")
    w(f"  · 有效行程 S = {d.get('S_mm',0):.0f} mm")
    w(f"  · 工作频率 f = {d.get('f_cycle',1):.1f} 次/min")
    w(f"  · 峰值功率 P_peak = {d.get('P_peak_kW',0):.3f} kW")
    w(f"  · 负载率 λ_p = {d.get('lambda_p',1):.2f}  {'(负载平稳)' if d.get('lambda_p',1)<=1.2 else '(中等波动，建议考虑蓄能器)' if d.get('lambda_p',1)<=1.5 else '(剧烈波动，强烈推荐蓄能器)'}")
    w(f"  · 环境温度 T_env = {d.get('T_env',30):.0f} ℃")
    w(f"  · 允许最高油温 T_max = {d.get('T_max',60):.0f} ℃")
    w("\n【2】压力与阀门");w("─"*60)
    w(f"  · 系统公称压力 p_sys = {d.get('p_sys',16):.1f} MPa")
    w(f"  · 机械效率 ηₘ = {d.get('eta_m',0.92):.2f}")
    w(f"  · 理论缸径(按负载压力) D_calc = {d.get('D_calc',0):.1f} mm")
    w(f"  · 预估流量(压力管) Q = {d.get('Q_fwd',0):.1f} L/min")
    w(f"  · 推荐压力管通径(4~6m/s) ≈ {d.get('d_pipe',0):.0f} mm")
    w("\n【2a】蓄能器");w("─"*60)
    if d.get('use_acc')=='yes':
        w(f"  · 已配置: {d.get('acc_type','')}")
        w(f"  · 公称容积 V₀(等温) = {d.get('acc_V0',0):.1f} L")
        if d.get('acc_V0_adi',0)>0:
            w(f"  · 公称容积 V₀(绝热,γ=1.4) = {d.get('acc_V0_adi',0):.1f} L")
    else:
        w("  · 未使用")
    w("\n【3】缸径计算结果");w("─"*60)
    w(f"  · 选定标准缸径(GB/T 2348) D = {d.get('D_std',0):.0f} mm")
    w(f"  · 活塞面积 A = {d.get('A_piston_mm2',0):.0f} mm²")
    w(f"  · 实际工作压力 p_actual = {d.get('p_actual',0):.2f} MPa")
    w(f"  · 实际推力 F_push = {d.get('F_push',0):.1f} kN")
    w("\n【4】活塞杆与速比");w("─"*60)
    w(f"  · 选定活塞杆直径 d = {d.get('d_std',0):.0f} mm")
    w(f"  · 实际拉力(有杆腔) F_pull = {d.get('F_pull',0):.1f} kN")
    w(f"  · 速比(无杆腔/有杆腔) φ = {d.get('phi',1):.2f}")
    w("\n【5】壁厚与材料");w("─"*60)
    w(f"  · 缸筒材料: {d.get('material','45#')}")
    w(f"  · 屈服强度 σs = {d.get('sigma_s',355):.0f} MPa")
    w(f"  · 安全系数 n = {d.get('n_safety',4):.1f}")
    w(f"  · 计算壁厚 δ = {d.get('wall_calc',0):.1f} mm")
    w(f"  · 选定标准壁厚 δ_std = {d.get('wall_std',0):.1f} mm")
    w(f"  · 缸筒外径 D_out = {d.get('D_out',0):.0f} mm")
    w(f"  · 壁厚公式: {d.get('wall_formula','')}")
    w("\n【6】稳定性校核");w("─"*60)
    w(f"  · 压杆总长 L = {d.get('L_rod',0):.0f} mm")
    w(f"  · 柔度 λ = {d.get('lam',0):.1f}")
    w(f"  · 临界失稳载荷 Pcr = {d.get('Pcr',0):.1f} kN")
    w(f"  · 稳定安全系数 n_st = {d.get('n_st',0):.2f}")
    w(f"  · 判定: {'✓ 通过 — 设计安全，活塞杆不会发生失稳弯曲' if d.get('buckle_pass') else '✗ 不通过 — 存在失稳风险，需加强设计'}")
    w("\n【7】密封与缓冲");w("─"*60)
    w(f"  · 密封形式: {d.get('seal_type','')}")
    w(f"  · 缓冲形式: {d.get('buffer_type','')}")
    w(f"  · 温度退化因子 η_T = {d.get('eta_T',1):.2f}")
    w(f"  · 油污退化因子 η_iso = {d.get('eta_iso',1):.2f}")
    w(f"  · 综合密封寿命 ≈ {d.get('seal_life',0):.0f} 小时")
    w("\n【8】泵阀匹配结果");w("─"*60)
    w(f"  · 前进流量(无杆腔进油) = {d.get('Q_fwd',0):.1f} L/min")
    w(f"  · 回程流量(有杆腔进油) = {d.get('Q_ret',0):.1f} L/min")
    w(f"  · ★ 设计流量 = {d.get('Q_design',0):.1f} L/min")
    w(f"  · 泵排量 Vg = {d.get('Vg_pump',0):.1f} mL/r")
    w(f"  · ★ 推荐泵类型: {d.get('pump_rec','')}")
    w(f"  · ★ 配用电机功率 ≈ {d.get('P_motor',0):.2f} kW")
    w(f"  · 压力管流速 = {d.get('v_pipe',0):.2f} m/s")
    w(f"  · 雷诺数 Re = {d.get('Re',0):.0f}")
    w(f"  · 管路总压降 Δp = {d.get('dp_total',0):.2f} bar")
    w("\n【9】热平衡与散热器");w("─"*60)
    w(f"  · 系统发热量 P_loss = {d.get('P_loss',0):.2f} kW")
    w(f"  · 油箱容积 V_tank = {d.get('V_tank',0):.0f} L")
    w(f"  · 自然散热能力 P_tank = {d.get('P_tank',0):.2f} kW")
    w(f"  · 预测平衡油温 T_eq ≈ {d.get('T_eq',0):.0f} ℃")
    if d.get('need_cooler'):
        w(f"  · ⚠ 需要加装散热器！推荐面积 A_cooler ≈ {d.get('A_cooler',0):.1f} m²")
        w(f"  · 推荐散热器类型: {d.get('cooler_type','')}")
    else:
        w("  · ✓ 自然冷却足够，无需散热器")
    w("\n【最终判定】");w("─"*60)
    issues=[]
    if not d.get('buckle_pass',True): issues.append("❌ [6] 稳定性校核不通过 — 活塞杆存在失稳风险")
    if d.get('need_cooler',False): issues.append("⚠ [9] 需加装散热器 — 自然冷却能力不足")
    if d.get('T_eq',0)>75 and d.get('eta_T',1)>0.6:
        issues.append("⚠ [7-9] 油温与密封矛盾 — 平衡油温偏高，密封寿命将急剧缩短")
    if not issues:
        w("  ★★★ 设计通过审查 ★★★")
    else:
        w("  ⛔ 存在以下问题需修正:")
        for iss in issues: w(f"    {iss}")
    w(f"\n  缸筒规格: D{d.get('D_std',0):.0f} × d{d.get('d_std',0):.0f} - δ{d.get('wall_std',0):.1f}")
    w(f"  系统压力: {d.get('p_sys',16):.1f} MPa")
    w(f"\n  《现代液压气动手册》2024 | GB/T 2348/2349/2346")
