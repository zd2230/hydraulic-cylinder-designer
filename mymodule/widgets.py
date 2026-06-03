#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 组件模块"""
import tkinter as tk
from tkinter import ttk
from mymodule.config import *

class InpRow(tk.Frame):
    def __init__(self,parent,label,unit="",default="",tip="",width=12):
        tk.Frame.__init__(self,parent,bg=C_PANEL)
        self.tip_text=tip
        self.var=tk.StringVar(value=str(default))
        self.lb=tk.Label(self,text=label,bg=C_PANEL,fg=C_TEXT,font=F(),width=20,anchor="w")
        self.lb.pack(side="left")
        self.entry=tk.Entry(self,textvariable=self.var,bg=C_CARD,fg=C_ACCENT2,font=F(),width=width,relief="solid",bd=1,insertbackground=C_TEXT,highlightcolor=C_ACCENT,highlightthickness=0)
        self.entry.pack(side="left",padx=4,ipady=2)
        if unit: tk.Label(self,text=unit,bg=C_PANEL,fg=C_TEXT2,font=F(),width=8).pack(side="left")
        if tip: self._add_tip()
        self.entry.bind("<Return>",lambda e:self.entry.tk_focusNext().focus())

    def warn(self,flag):
        """高亮标记：红色边框表示必填"""
        self.entry.config(highlightcolor=C_RED if flag else C_ACCENT,
                          highlightbackground=C_RED if flag else C_PANEL,
                          highlightthickness=2 if flag else 0)
    def _add_tip(self):
        lbl=tk.Label(self,text="ⓘ",bg=C_PANEL,fg=C_ACCENT,font=F(9),cursor="hand2")
        lbl.pack(side="left",padx=2)
        self._bind_tip(lbl)
    def _bind_tip(self,widget):
        def show(e):
            self.tip=tk.Toplevel(self)
            self.tip.wm_overrideredirect(True)
            self.tip.wm_geometry(f"+{self.winfo_pointerx()+15}+{self.winfo_pointery()+5}")
            self.tip.configure(bg=C_PANEL)
            tk.Label(self.tip,text=self.tip_text,bg=C_PANEL,fg=C_TEXT,font=F(9),wraplength=320,padx=8,pady=6).pack()
        def hide(e):
            if hasattr(self,"tip") and self.tip: self.tip.destroy(); self.tip=None
        widget.bind("<Enter>",show); widget.bind("<Leave>",hide)
    def getf(self,default=0.0):
        try:
            v=self.var.get().strip()
            return float(v) if v else default
        except: return default
    def get_valid_f(self,label="输入",min_val=0,max_val=1e9):
        try:
            v=self.var.get().strip()
            if not v: return None,f"{label}不能为空"
            val=float(v)
            if val<min_val: return None,f"{label}不能小于{min_val}"
            if val>max_val: return None,f"{label}不能大于{max_val}"
            return val,None
        except: return None,f"{label}请输入有效数字"
    def set(self,value,dec=2):
        if isinstance(value,str): self.var.set(value)
        else: self.var.set(f"{value:.{dec}f}")

class Res(tk.Frame):
    def __init__(self,parent,label,unit="",color=C_GREEN,fsize=10):
        tk.Frame.__init__(self,parent,bg=C_PANEL)
        self.var=tk.StringVar(value="--")
        tk.Label(self,text=label,bg=C_PANEL,fg=C_TEXT,font=F(fsize),anchor="w").pack(side="left")
        self.vl=tk.Label(self,textvariable=self.var,bg=C_PANEL,fg=color,font=F(fsize,True),anchor="e",width=22)
        self.vl.pack(side="left")
        if unit: tk.Label(self,text=unit,bg=C_PANEL,fg=C_TEXT2,font=F(fsize)).pack(side="left")
    def set(self,value,dec=2):
        if isinstance(value,str): self.var.set(value)
        else: self.var.set(f"{value:.{dec}f}")

class Card(tk.LabelFrame):
    def __init__(self,parent,title):
        tk.LabelFrame.__init__(self,parent,text=f"  {title}  ",bg=C_PANEL,fg=C_ACCENT,font=F(10,True),relief="solid",padx=8,pady=4)

    def add_copy_btn(self,app):
        """在卡片右上角添加'复制'按钮，复制卡片内所有Res的文本"""
        btn=tk.Button(self,text="📋 复制",bg=C_CARD,fg=C_ACCENT,font=F(8),relief="flat",
                      padx=6,pady=0,cursor="hand2",command=lambda:_copy_card(self,app))
        btn.place(relx=1.0,x=-4,y=0,anchor="ne")
    @staticmethod
    def copy_line(w,name,val,unit):
        w.insert("end",f"  · {name} = {val} {unit}\n")

def _copy_card(card,app):
    """收集卡片下所有Res组件的内容到剪贴板"""
    lines=[]
    for child in card.winfo_children():
        if isinstance(child,Res):
            label=child.lb.cget("text")
            val=child.var.get()
            # Find unit label
            unit=""
            for c in child.winfo_children():
                if isinstance(c, tk.Label) and c is not child.lb and c is not child.vl:
                    unit=c.cget("text")
                    break
            lines.append(f"  {label}: {val} {unit}".strip())
        elif isinstance(child,tk.Frame):
            for sub in child.winfo_children():
                if isinstance(sub,tk.Label):
                    txt=sub.cget("text")
                    if txt and txt!="": lines.append(f"  {txt}")
    txt="\n".join(lines)
    app.root.clipboard_clear()
    app.root.clipboard_append(txt)
    app.msg("已复制到剪贴板")

def step_title(parent,cn,en):
    hdr=tk.Frame(parent,bg=C_BG)
    tk.Label(hdr,text=cn,bg=C_BG,fg=C_TEXT,font=F(16,True)).pack(anchor="w")
    tk.Label(hdr,text=en,bg=C_BG,fg=C_TEXT2,font=F(10)).pack(anchor="w")
    return hdr

def big_btn(parent,text,cmd,color=C_ACCENT):
    return tk.Button(parent,text=f"  {text}  ",command=cmd,bg=color,fg="white",font=F(11,True),relief="flat",padx=20,pady=8,cursor="hand2")

class ScrollFrame(tk.Frame):
    def __init__(self,parent):
        tk.Frame.__init__(self,parent,bg=C_BG)
        self.pack(fill="both",expand=True)
        self.sb=tk.Scrollbar(self,orient="vertical")
        self.canvas=tk.Canvas(self,bg=C_BG,highlightthickness=0,yscrollcommand=self.sb.set)
        self.canvas.pack(side="left",fill="both",expand=True)
        self.sb.pack(side="right",fill="y")
        self.sb.configure(command=self.canvas.yview)
        self.scroll_frame=tk.Frame(self.canvas,bg=C_BG)
        self.sf_id=self.canvas.create_window(0,0,window=self.scroll_frame,anchor="nw")
        self.canvas.bind("<Configure>",lambda e:self.canvas.itemconfig(self.sf_id,width=e.width))
        self.scroll_frame.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        def _bw(event): self.canvas.yview_scroll(int(-1*(event.delta/120)),"units")
        self.canvas.bind("<Enter>",lambda e:self.canvas.bind_all("<MouseWheel>",_bw))
        self.canvas.bind("<Leave>",lambda e:self.canvas.unbind_all("<MouseWheel>"))
