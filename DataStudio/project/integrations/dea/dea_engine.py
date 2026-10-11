"""Auditable DEA model implementations used by the desktop application."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linprog


@dataclass
class DEAResult:
    dmu: str
    period: str
    model: str
    orientation: str
    rts: str
    score: float
    radial_factor: float | None
    status: str
    lambdas: dict[str, float]
    input_slacks: dict[str, float]
    output_slacks: dict[str, float]
    input_targets: dict[str, float]
    output_targets: dict[str, float]
    crs_score: float | None = None
    vrs_score: float | None = None
    scale_efficiency: float | None = None
    note: str = ""


def _rts_constraints(n: int, rts: str, offset: int = 0):
    """Return equality/inequality rows imposing a returns-to-scale assumption."""
    rts = rts.upper()
    a_eq = b_eq = a_ub = b_ub = None
    ones = np.zeros(n + offset)
    ones[:n] = 1.0
    if rts == "VRS":
        a_eq, b_eq = [ones], [1.0]
    elif rts == "NIRS":
        a_ub, b_ub = [ones], [1.0]
    elif rts == "NDRS":
        a_ub, b_ub = [-ones], [-1.0]
    elif rts != "CRS":
        raise ValueError(f"Unsupported returns-to-scale option: {rts}")
    return a_eq, b_eq, a_ub, b_ub


def _base_constraints(n, m, s, rts, offset=0):
    eq, beq, ub, bub = _rts_constraints(n, rts, offset)
    return (None if eq is None else np.asarray(eq), None if beq is None else np.asarray(beq),
            None if ub is None else np.asarray(ub), None if bub is None else np.asarray(bub))


def _radial(X, Y, names, target_index, orientation="Input", rts="CRS", ref_indices=None,
            tolerance=1e-7, solve_slacks=True):
    """Radial envelopment DEA with a lexicographic second phase for slacks."""
    n_all, m = X.shape
    s = Y.shape[1]
    ref_indices = list(range(n_all)) if ref_indices is None else list(ref_indices)
    xr, yr = X[target_index], Y[target_index]
    Xr, Yr = X[ref_indices], Y[ref_indices]
    n = len(ref_indices)
    inp = orientation.lower() == "input"
    if orientation.lower() not in {"input", "output"}:
        raise ValueError("Radial DEA supports Input or Output orientation.")

    # Phase I: optimize the radial contraction theta or expansion phi.
    c = np.zeros(n + 1)
    c[-1] = 1.0 if inp else -1.0
    A_ub, b_ub = [], []
    if inp:
        for i in range(m):
            row = np.zeros(n + 1); row[:n] = Xr[:, i]; row[-1] = -xr[i]
            A_ub.append(row); b_ub.append(0.0)
        for r in range(s):
            row = np.zeros(n + 1); row[:n] = -Yr[:, r]
            A_ub.append(row); b_ub.append(-yr[r])
    else:
        for i in range(m):
            row = np.zeros(n + 1); row[:n] = Xr[:, i]
            A_ub.append(row); b_ub.append(xr[i])
        for r in range(s):
            row = np.zeros(n + 1); row[:n] = -Yr[:, r]; row[-1] = yr[r]
            A_ub.append(row); b_ub.append(0.0)
    A_eq0, b_eq0, A_rts, b_rts = _base_constraints(n, m, s, rts, 1)
    if A_rts is not None:
        A_ub.extend(A_rts); b_ub.extend(b_rts)
    phase1 = linprog(c, A_ub=np.asarray(A_ub), b_ub=np.asarray(b_ub),
                     A_eq=A_eq0, b_eq=b_eq0, bounds=[(0, None)]*n + [(0, None)], method="highs")
    if not phase1.success:
        raise ValueError(f"LP could not be solved for {names[target_index]}: {phase1.message}")
    factor = float(phase1.x[-1])
    lambda1 = phase1.x[:n]
    if not solve_slacks:
        return factor, lambda1, np.zeros(m), np.zeros(s), ref_indices

    # Phase II: hold the radial score fixed and maximize normalized total slacks.
    # Variables are [lambda, input slacks, output slacks].
    q = n + m + s
    c2 = np.zeros(q)
    input_scale = np.maximum(np.max(np.abs(X), axis=0), 1.0)
    output_scale = np.maximum(np.max(np.abs(Y), axis=0), 1.0)
    c2[n:n+m] = -1.0 / input_scale
    c2[n+m:] = -1.0 / output_scale
    Aeq, beq = [], []
    for i in range(m):
        row = np.zeros(q); row[:n] = Xr[:, i]; row[n+i] = 1.0
        if inp:
            row[-1] = 0.0
            be = factor * xr[i]
        else:
            be = xr[i]
        Aeq.append(row); beq.append(be)
    for r in range(s):
        row = np.zeros(q); row[:n] = Yr[:, r]; row[n+m+r] = -1.0
        be = yr[r] if inp else factor * yr[r]
        Aeq.append(row); beq.append(be)
    Aeq = np.asarray(Aeq); beq = np.asarray(beq)
    if rts.upper() == "VRS":
        row = np.zeros(q); row[:n] = 1.0
        Aeq = np.vstack([Aeq, row]); beq = np.r_[beq, 1.0]
    else:
        # NIRS/NDRS must remain inequalities, not equalities, in the slack phase.
        pass
    Aub2, bub2 = [], []
    if rts.upper() == "NIRS":
        row = np.zeros(q); row[:n] = 1.0; Aub2.append(row); bub2.append(1.0)
    elif rts.upper() == "NDRS":
        row = np.zeros(q); row[:n] = -1.0; Aub2.append(row); bub2.append(-1.0)
    phase2 = linprog(c2, A_ub=np.asarray(Aub2) if Aub2 else None,
                     b_ub=np.asarray(bub2) if bub2 else None,
                     A_eq=Aeq, b_eq=beq, bounds=[(0,None)]*q, method="highs")
    if phase2.success:
        lam = phase2.x[:n]
        si = phase2.x[n:n+m]
        so = phase2.x[n+m:]
    else:
        lam = lambda1
        proj_x = lam @ Xr
        proj_y = lam @ Yr
        si = np.maximum((factor*xr if inp else xr) - proj_x, 0.0)
        so = np.maximum(proj_y - (yr if inp else factor*yr), 0.0)
    return factor, lam, si, so, ref_indices


def _sbm(X, Y, names, target_index, rts="CRS"):
    """Input-oriented SBM using a Charnes-Cooper linearization."""
    if not np.all(X[target_index] > 0) or not np.all(Y[target_index] > 0):
        raise ValueError("Input-oriented SBM requires positive target inputs and outputs.")
    n, m = X.shape; s = Y.shape[1]
    x0, y0 = X[target_index], Y[target_index]
    # Variables: scaled lambdas, scaled input slacks, scaled output slacks, t.
    q = n + m + s + 1; t_idx = q - 1
    c = np.zeros(q); c[t_idx] = 1.0
    c[n:n+m] = -1.0 / (m*x0)
    Aeq, beq = [], []
    for i in range(m):
        row = np.zeros(q); row[:n] = X[:, i]; row[n+i] = 1.0; row[t_idx] = -x0[i]
        Aeq.append(row); beq.append(0.0)
    for r in range(s):
        row = np.zeros(q); row[:n] = Y[:, r]; row[n+m+r] = -1.0; row[t_idx] = -y0[r]
        Aeq.append(row); beq.append(0.0)
    row = np.zeros(q); row[t_idx] = 1.0; row[n+m:n+m+s] = 1.0/(s*y0)
    Aeq.append(row); beq.append(1.0)
    if rts.upper() == "VRS":
        row = np.zeros(q); row[:n] = 1.0; row[t_idx] = -1.0
        Aeq.append(row); beq.append(0.0)
    Aub, bub2 = [], []
    if rts.upper() == "NIRS":
        row = np.zeros(q); row[:n] = 1.0; row[t_idx] = -1.0; Aub.append(row); bub2.append(0.0)
    elif rts.upper() == "NDRS":
        row = np.zeros(q); row[:n] = -1.0; row[t_idx] = 1.0; Aub.append(row); bub2.append(0.0)
    res = linprog(c, A_ub=np.asarray(Aub) if Aub else None, b_ub=np.asarray(bub2) if bub2 else None,
                  A_eq=np.asarray(Aeq), b_eq=np.asarray(beq), bounds=[(0,None)]*q, method="highs")
    if not res.success:
        raise ValueError(f"SBM could not be solved for {names[target_index]}: {res.message}")
    t = max(float(res.x[t_idx]), 1e-12)
    lam = res.x[:n]/t
    si = res.x[n:n+m]/t
    so = res.x[n+m:n+m+s]/t
    rho = float(res.fun)
    return rho, lam, si, so


def _additive(X, Y, names, target_index, rts="CRS"):
    """Normalized additive DEA slack model. Score is a diagnostic, not radial efficiency."""
    n,m = X.shape; s=Y.shape[1]
    x0,y0=X[target_index],Y[target_index]
    q=n+m+s
    c=np.zeros(q)
    c[n:n+m]=-1/np.maximum(np.max(X,axis=0),1.0)
    c[n+m:]=-1/np.maximum(np.max(Y,axis=0),1.0)
    Aeq=[]; beq=[]
    for i in range(m):
        row=np.zeros(q); row[:n]=X[:,i]; row[n+i]=1; Aeq.append(row); beq.append(x0[i])
    for r in range(s):
        row=np.zeros(q); row[:n]=Y[:,r]; row[n+m+r]=-1; Aeq.append(row); beq.append(y0[r])
    Aub=[]; bub=[]
    if rts.upper()=="VRS":
        row=np.zeros(q); row[:n]=1; Aeq.append(row); beq.append(1)
    elif rts.upper()=="NIRS":
        row=np.zeros(q); row[:n]=1; Aub.append(row); bub.append(1)
    elif rts.upper()=="NDRS":
        row=np.zeros(q); row[:n]=-1; Aub.append(row); bub.append(-1)
    elif rts.upper()!="CRS": raise ValueError(f"Unsupported RTS: {rts}")
    res=linprog(c,A_ub=np.asarray(Aub) if Aub else None,b_ub=np.asarray(bub) if bub else None,
                A_eq=np.asarray(Aeq),b_eq=np.asarray(beq),bounds=[(0,None)]*q,method="highs")
    if not res.success: raise ValueError(f"Additive DEA could not be solved for {names[target_index]}: {res.message}")
    return max(0.0,float(-res.fun)),res.x[:n],res.x[n:n+m],res.x[n+m:]


def solve_cross_efficiency(X, Y, names, aggregate="Mean", epsilon=0.0):
    """CCR multiplier cross-efficiency; returns a matrix and aggregate peer scores."""
    n,m=X.shape; s=Y.shape[1]
    matrix=np.zeros((n,n)); weight_rows=[]
    for i in range(n):
        # Variables [u_1..u_s, v_1..v_m], normalize v*x_i=1.
        c=np.r_[ -Y[i], np.zeros(m)]
        Aub=[]
        for j in range(n): Aub.append(np.r_[Y[j],-X[j]])
        Aeq=[np.r_[np.zeros(s),X[i]]]; beq=[1.0]
        res=linprog(c,A_ub=np.asarray(Aub),b_ub=np.zeros(n),A_eq=np.asarray(Aeq),b_eq=np.asarray(beq),
                    bounds=[(epsilon,None)]*(s+m),method="highs")
        if not res.success: raise ValueError(f"Cross-efficiency failed for {names[i]}: {res.message}")
        u,v=res.x[:s],res.x[s:]
        weight_rows.append((u,v))
        den=X@v
        matrix[i,:]=np.divide(Y@u,den,out=np.full(n,np.nan),where=den>1e-12)
    fn=np.nanmean if aggregate.lower()=="mean" else np.nanmedian
    return matrix,fn(matrix,axis=0),weight_rows


def solve_dataset(df, input_cols, output_cols, model="CCR", orientation="Input", rts="CRS",
                  tolerance=1e-6, cross_aggregate="Mean") -> dict[str, Any]:
    """Calculate selected DEA model(s) and return a workbook-ready result structure."""
    model=model.strip(); orientation=orientation.title(); rts=rts.upper()
    names=df["DMU_ID"].astype(str).tolist()
    periods=df["Period"].fillna("").astype(str).tolist() if "Period" in df else [""]*len(df)
    X=df[input_cols].to_numpy(dtype=float); Y=df[output_cols].to_numpy(dtype=float)
    if len(names)<2: raise ValueError("At least two DMUs are required.")
    if not np.isfinite(X).all() or not np.isfinite(Y).all(): raise ValueError("Input and output values must all be numeric and non-missing.")
    if (X<0).any() or (Y<0).any(): raise ValueError("This model set requires non-negative inputs and outputs.")
    if (X.sum(axis=1)<=0).any() or (Y.sum(axis=1)<=0).any(): raise ValueError("Each DMU must have a positive total input and output.")
    results=[]; extra={}
    if model=="Malmquist_MPI":
        return _solve_malmquist(df,input_cols,output_cols,tolerance)
    if model=="CrossEfficiency":
        if rts!="CRS": raise ValueError("CrossEfficiency currently supports CRS only.")
        matrix,agg,weights=solve_cross_efficiency(X,Y,names,cross_aggregate)
        return {"model":model,"orientation":"Multiplicative CCR","rts":"CRS","results":[],
                "cross_matrix":matrix,"cross_aggregate":agg,"cross_weights":weights,
                "names":names,"input_cols":input_cols,"output_cols":output_cols,"input_df":df}
    if model=="SBM" and orientation!="Input": raise ValueError("The current SBM implementation is input-oriented.")
    if model=="SuperEfficiency" and orientation!="Input": raise ValueError("The current SuperEfficiency implementation is input-oriented.")
    for idx,name in enumerate(names):
        ref=list(range(len(names)))
        if model=="SuperEfficiency": ref=[j for j in ref if j!=idx]
        if model=="SBM":
            score,lam,si,so=_sbm(X,Y,names,idx,rts)
            factor=None
        elif model=="Additive":
            score,lam,si,so=_additive(X,Y,names,idx,rts)
            factor=None
        elif model in {"CCR","BCC","SuperEfficiency"}:
            use_rts="CRS" if model=="CCR" else ("VRS" if model=="BCC" else rts)
            factor,lam,si,so,ref=_radial(X,Y,names,idx,orientation,use_rts,ref,tolerance)
            score=factor if orientation=="Input" else 1.0/factor
            rts=use_rts
        else:
            raise ValueError(f"Unsupported model: {model}")
        lam_map={names[j]:float(v) for j,v in zip(ref,lam) if v>tolerance}
        xproj=np.asarray(lam)@X[ref]
        yproj=np.asarray(lam)@Y[ref]
        si_map={c:float(v) for c,v in zip(input_cols,si)}
        so_map={c:float(v) for c,v in zip(output_cols,so)}
        if model=="Additive":
            xt,yt=xproj,yproj
            status="Efficient" if score<=tolerance else "Inefficient"
        else:
            slack_total=float(np.sum(si)+np.sum(so))
            if model=="SuperEfficiency":
                if score>1+tolerance: status="Super-efficient"
                elif score>=1-tolerance: status="Efficient frontier unit"
                else: status="Inefficient"
            elif model=="SBM": status="Efficient" if score>=1-tolerance else "Inefficient"
            elif score>=1-tolerance and slack_total<=tolerance: status="Strongly efficient"
            elif score>=1-tolerance: status="Weakly efficient"
            else: status="Inefficient"
            xt=xproj; yt=yproj
        crs_score=vrs_score=scale_eff=None
        if model in {"CCR","BCC"}:
            cfac,_,_,_,_=_radial(X,Y,names,idx,orientation,"CRS",None,tolerance,False)
            vfac,_,_,_,_=_radial(X,Y,names,idx,orientation,"VRS",None,tolerance,False)
            crs_score=float(cfac if orientation=="Input" else 1.0/cfac)
            vrs_score=float(vfac if orientation=="Input" else 1.0/vfac)
            scale_eff=float(crs_score/vrs_score) if vrs_score else None
        results.append(DEAResult(name,periods[idx],model,orientation,rts,float(score),None if factor is None else float(factor),status,
            lam_map,si_map,so_map,{c:float(v) for c,v in zip(input_cols,xt)},
            {c:float(v) for c,v in zip(output_cols,yt)},crs_score,vrs_score,scale_eff))
    return {"model":model,"orientation":orientation,"rts":rts,"results":results,
            "input_cols":input_cols,"output_cols":output_cols,"names":names,"input_df":df,"extra":extra}


def _solve_malmquist(df,input_cols,output_cols,tolerance):
    """Adjacent-period CRS output-distance MPI with standard EC × TC decomposition."""
    periods=sorted(df["Period"].dropna().astype(str).unique(),key=lambda x:(not x.isdigit(),int(x) if x.isdigit() else x))
    if len(periods)<2: raise ValueError("Malmquist MPI requires at least two periods.")
    Xall=df[input_cols].to_numpy(float); Yall=df[output_cols].to_numpy(float)
    names_all=df["DMU_ID"].astype(str).to_numpy(); p_all=df["Period"].astype(str).to_numpy()
    rows=[]
    for t0,t1 in zip(periods[:-1],periods[1:]):
        ids0={n:i for i,n in enumerate(np.where(p_all==t0)[0])}
        ids1={n:i for i,n in enumerate(np.where(p_all==t1)[0])}
        idx0=np.where(p_all==t0)[0]; idx1=np.where(p_all==t1)[0]
        common=sorted(set(names_all[idx0])&set(names_all[idx1]))
        if not common: raise ValueError(f"No DMUs appear in both periods {t0} and {t1}.")
        if set(names_all[idx0]) != set(names_all[idx1]):
            raise ValueError(f"Malmquist MPI requires a balanced panel for periods {t0} and {t1}; DMU sets differ.")
        # Each frontier consists of observations in its own period.
        Xt,Yt=Xall[idx0],Yall[idx0]; Xt1,Yt1=Xall[idx1],Yall[idx1]
        for dmu in common:
            i0=idx0[np.where(names_all[idx0]==dmu)[0][0]]
            i1=idx1[np.where(names_all[idx1]==dmu)[0][0]]
            # _radial indexes the evaluated point in arrays containing the reference set.
            def dist(front_x,front_y,eval_x,eval_y):
                xx=np.vstack([front_x,eval_x]); yy=np.vstack([front_y,eval_y]); nn=[f"F{k}" for k in range(len(front_x))]+[dmu]
                # target is appended; evaluator can appear in the frontier as well.
                fac,_,_,_,_=_radial(xx,yy,nn,len(nn)-1,"Output","CRS",list(range(len(front_x))),tolerance,False)
                return 1.0/fac
            d_t_t=dist(Xt,Yt,Xall[i0],Yall[i0])
            d_t_t1=dist(Xt,Yt,Xall[i1],Yall[i1])
            d_t1_t=dist(Xt1,Yt1,Xall[i0],Yall[i0])
            d_t1_t1=dist(Xt1,Yt1,Xall[i1],Yall[i1])
            mpi=float(np.sqrt((d_t_t1/d_t_t)*(d_t1_t1/d_t1_t)))
            ec=float(d_t1_t1/d_t_t)
            tc=float(mpi/ec) if ec else np.nan
            rows.append({"DMU_ID":dmu,"Period_t":t0,"Period_t1":t1,"D_t(x_t,y_t)":d_t_t,
                         "D_t(x_t1,y_t1)":d_t_t1,"D_t1(x_t,y_t)":d_t1_t,
                         "D_t1(x_t1,y_t1)":d_t1_t1,"EC":ec,"TC":tc,"MPI":mpi,
                         "Interpretation":"Productivity improved" if mpi>1+tolerance else ("No change" if abs(mpi-1)<=tolerance else "Productivity declined")})
    return {"model":"Malmquist_MPI","orientation":"Output distance","rts":"CRS",
            "malmquist_rows":rows,"input_cols":input_cols,"output_cols":output_cols,"input_df":df}
