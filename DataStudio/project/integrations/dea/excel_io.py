"""Excel import, validation and auditable result workbook export."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xlsxwriter

MODEL_ALIASES = {
    "malmquist": "Malmquist_MPI", "malmquist_mpi": "Malmquist_MPI",
    "cross efficiency": "CrossEfficiency", "cross_efficiency": "CrossEfficiency",
    "network dea": "NetworkDEA", "networkdea": "NetworkDEA",
    "super efficiency": "SuperEfficiency", "super_efficiency": "SuperEfficiency",
}


def _read_sheets(path: str | Path):
    try:
        book = pd.ExcelFile(path)
    except Exception as exc:
        raise ValueError(f"Could not open the Excel workbook: {exc}") from exc
    sheets = {name.strip().lower(): name for name in book.sheet_names}
    data_name = sheets.get("data")
    if not data_name:
        raise ValueError("The workbook must contain a sheet named 'Data'.")
    data = pd.read_excel(path, sheet_name=data_name)
    data.columns = [str(c).strip() for c in data.columns]
    config = {}
    if "config" in sheets:
        cdf = pd.read_excel(path, sheet_name=sheets["config"])
        if len(cdf.columns) >= 2:
            for _, row in cdf.iterrows():
                if pd.notna(row.iloc[0]) and pd.notna(row.iloc[1]):
                    config[str(row.iloc[0]).strip()] = row.iloc[1]
    variables = pd.DataFrame()
    if "variables" in sheets:
        variables = pd.read_excel(path, sheet_name=sheets["variables"])
        variables.columns = [str(c).strip() for c in variables.columns]
    return data, config, variables, book.sheet_names


def inspect_template(path: str | Path) -> dict[str, Any]:
    data, config, variables, sheet_names = _read_sheets(path)
    periods=[]
    if "Period" in data.columns:
        periods=sorted({p.strip() for p in data.loc[data.get("DMU_ID", pd.Series(index=data.index)).notna(),"Period"].dropna().astype(str).tolist() if p.strip()})
    if not variables.empty and {"Variable_ID", "Role"}.issubset(variables.columns):
        selected=variables.copy()
        if "Include (Y/N)" in selected:
            selected=selected[selected["Include (Y/N)"].fillna("Y").astype(str).str.upper()!="N"]
        selected=selected[selected.get("Variable_Name", pd.Series(index=selected.index)).fillna("").astype(str).str.strip().ne("")]
        inputs=int(selected["Role"].astype(str).str.lower().eq("input").sum())
        outputs=int(selected["Role"].astype(str).str.lower().isin(["output","desirable_output"]).sum())
    else:
        inputs=sum(str(c).startswith("Input_") for c in data.columns)
        outputs=sum(str(c).startswith("Output_") for c in data.columns)
    return {"config":config,"periods":periods,"rows":int(data["DMU_ID"].notna().sum()) if "DMU_ID" in data else 0,
            "input_count":inputs,"output_count":outputs,"columns":list(data.columns),"sheets":sheet_names}


def load_dea_workbook(path: str | Path, model_override: str | None = None,
                      orientation_override: str | None = None,
                      rts_override: str | None = None) -> dict[str, Any]:
    """Read the agreed template and return validated inputs and selected options."""
    data, config, variables, sheet_names = _read_sheets(path)
    if "DMU_ID" not in data.columns:
        raise ValueError("The Data sheet is missing the required 'DMU_ID' column. Add a unique ID column for each decision-making unit.")
    data = data.loc[data["DMU_ID"].notna()].copy()
    data["DMU_ID"] = data["DMU_ID"].astype(str).str.strip()
    if "Period" not in data:
        data["Period"] = ""
    data["Period"] = data["Period"].fillna("").astype(str).str.strip()
    if data.empty:
        raise ValueError("No observations found. Enter at least two complete DMUs on the Data sheet first.")
    if (data["DMU_ID"] == "").any():
        raise ValueError("Some data rows have a blank DMU_ID. Enter a unique identifier for every observation row.")
    if len(data) < 2:
        raise ValueError("DEA requires at least two DMUs. Add another complete observation before running the analysis.")

    model = str(model_override or config.get("Model_Family", "CCR")).strip()
    model = MODEL_ALIASES.get(model.lower(), model)
    orientation = str(orientation_override or config.get("Orientation", "Input")).strip().title()
    rts = str(rts_override or config.get("Returns_to_Scale", "CRS")).strip().upper()
    tolerance = float(config.get("Solver_Tolerance", 1e-6))

    if model == "NetworkDEA":
        raise ValueError("Network DEA is listed in the template, but its exact network formulation is not yet selected. Use CCR/BCC/SBM or provide the Network DEA theory to enable it.")
    if model not in {"CCR", "BCC", "SBM", "Additive", "CrossEfficiency", "SuperEfficiency", "Malmquist_MPI"}:
        raise ValueError(f"Unsupported model family: {model}")
    allowed_orientations={"Input","Output"}
    if model in {"Additive","CrossEfficiency","Malmquist_MPI"}: allowed_orientations.add("Non-Oriented")
    if orientation not in allowed_orientations:
        raise ValueError("This model requires Input, Output, or Non-Oriented orientation as applicable.")
    if rts not in {"CRS", "VRS", "NIRS", "NDRS"}:
        raise ValueError("Returns to scale must be CRS, VRS, NIRS, or NDRS.")

    input_cols, output_cols, bad_cols = [], [], []
    if not variables.empty and {"Variable_ID", "Role"}.issubset(variables.columns):
        for _, row in variables.iterrows():
            vid = row.get("Variable_ID")
            role = row.get("Role")
            if pd.isna(vid) or pd.isna(role):
                continue
            include = str(row.get("Include (Y/N)", "Y")).strip().upper()
            label = row.get("Variable_Name")
            # Blank names mean that the reserved template column is unused.
            if include == "N" or pd.isna(label) or not str(label).strip():
                continue
            vid, role = str(vid).strip(), str(role).strip().lower()
            if vid not in data.columns:
                raise ValueError(f"Variables lists '{vid}', but the Data sheet has no matching column.")
            if role == "input": input_cols.append(vid)
            elif role in {"desirable_output", "output"}: output_cols.append(vid)
            elif role in {"undesirable_output", "intermediate"}: bad_cols.append((vid, role))
    else:
        input_cols = [c for c in data.columns if c.startswith("Input_")]
        output_cols = [c for c in data.columns if c.startswith("Output_")]

    if bad_cols:
        labels = ", ".join(c for c, _ in bad_cols)
        raise ValueError(f"Selected model does not yet implement undesirable/intermediate variables: {labels}.")
    if not input_cols or not output_cols:
        raise ValueError("Define at least one input and one desirable output. Name Data columns with the prefixes 'Input_' and 'Output_', for example Input_Staff_FTE and Output_Graduates.")
    for c in input_cols + output_cols:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    missing=data[input_cols+output_cols].isna().any(axis=1)
    if missing.any():
        examples=", ".join(data.loc[missing,"DMU_ID"].astype(str).head(8))
        raise ValueError(f"Selected input/output cells are blank or non-numeric in {int(missing.sum())} DMU-period row(s). Examples: {examples}. Check the yellow cells and enter numbers only.")
    values=data[input_cols+output_cols].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Selected inputs and outputs must be finite numbers. Remove NaN or infinite values from the Data sheet.")
    if (values<0).any():
        raise ValueError("Selected inputs and outputs cannot be negative in the supported models. Correct the affected Data cells.")
    if (data[input_cols].sum(axis=1)<=0).any() or (data[output_cols].sum(axis=1)<=0).any():
        raise ValueError("Each DMU must have a positive total for inputs and outputs. Check rows containing only zero values.")
    if model=="SBM" and ((data[input_cols]<=0).any().any() or (data[output_cols]<=0).any().any()):
        raise ValueError("Input-oriented SBM requires every selected input and output value to be greater than zero. Replace zero values or choose another model.")
    if data.duplicated(["DMU_ID", "Period"]).any():
        dups = data.loc[data.duplicated(["DMU_ID", "Period"], keep=False), ["DMU_ID", "Period"]].head(8)
        examples = "; ".join(f"{r.DMU_ID} / {r.Period or '(blank period)'}" for r in dups.itertuples())
        raise ValueError(f"DMU_ID and Period must be unique. Duplicate examples: {examples}")
    warnings=[]
    n,m,s=len(data),len(input_cols),len(output_cols)
    minimum=max(m*s,2*(m+s))
    if n<minimum:
        warnings.append(f"There are {n} DMUs for {m} input(s) and {s} output(s). DEA results may have limited discriminatory power with small samples; a common rule of thumb is at least max(inputs × outputs, 2 × (inputs + outputs)) = {minimum} DMUs.")
    return {"data": data.reset_index(drop=True), "config": config, "variables": variables,
            "model": model, "orientation": orientation, "rts": rts,
            "tolerance": tolerance, "input_cols": input_cols, "output_cols": output_cols,
            "source_path": str(path), "sheet_names": sheet_names,"warnings":warnings}


def _styles(wb):
    return {
        "title": wb.add_format({"bold": True, "font_size": 15, "font_color": "#17365D"}),
        "subtitle": wb.add_format({"italic": True, "font_color": "#526174", "text_wrap": True}),
        "header": wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "border": 0, "text_wrap": True, "valign": "vcenter"}),
        "input": wb.add_format({"bg_color": "#FFF2CC", "num_format": "0.000000"}),
        "num": wb.add_format({"num_format": "0.000000"}),
        "pct": wb.add_format({"num_format": "0.00%"}),
        "section": wb.add_format({"bold": True, "font_color": "#17365D", "bg_color": "#D9EAF7"}),
        "wrap": wb.add_format({"text_wrap": True, "valign": "top"}),
        "formula": wb.add_format({"font_name": "Consolas", "font_size": 9, "text_wrap": True, "valign": "top"}),
        "note": wb.add_format({"font_color": "#526174", "text_wrap": True, "valign": "top"}),
    }


def _sheet_base(ws, title, subtitle, styles):
    ws.hide_gridlines(2); ws.freeze_panes(3, 0); ws.set_row(0, 24)
    ws.write(0, 0, title, styles["title"]); ws.write(1, 0, subtitle, styles["subtitle"])


def export_results(output_path: str | Path, result: dict[str, Any], input_bundle: dict[str, Any]):
    """Write a result workbook with numeric results, Excel formulas and model audit notes."""
    output_path = Path(output_path); output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(output_path))
    st = _styles(wb)
    model=result["model"]; orientation=result.get("orientation",""); rts=result.get("rts","")
    summary=wb.add_worksheet("Summary")
    summary.hide_gridlines(2); summary.set_column("A:A",28); summary.set_column("B:B",27); summary.set_column("C:C",90)
    summary.write("A1","DEA Analysis Results",st["title"])
    summary.write("A3","Model family",st["section"]); summary.write("B3",model)
    summary.write("A4","Orientation",st["section"]); summary.write("B4",orientation)
    summary.write("A5","Returns to scale",st["section"]); summary.write("B5",rts)
    summary.write("A6","Input variables",st["section"]); summary.write("B6",", ".join(input_bundle["input_cols"]))
    summary.write("A7","Output variables",st["section"]); summary.write("B7",", ".join(input_bundle["output_cols"]))
    summary.write("A9","Interpretation",st["section"])
    summary.write("B9", "Efficiency scores are model-specific. CCR/BCC radial scores use 1 as the frontier; input-oriented scores below 1 indicate proportional input reduction potential. Output-oriented efficiency is reported as 1/phi. SBM uses its own non-radial score. Additive slack scores are not on the same scale as radial scores.",st["wrap"])
    summary.set_row(8, 60)

    if model == "Malmquist_MPI":
        ws=wb.add_worksheet("Malmquist_MPI"); _sheet_base(ws,"Malmquist Productivity Index","Adjacent observed periods; CRS output distance functions. Values above 1 indicate productivity growth under this convention.",st)
        headers=["DMU_ID","Period_t","Period_t+1","D_t(x_t,y_t)","D_t(x_t+1,y_t+1)","D_t+1(x_t,y_t)","D_t+1(x_t+1,y_t+1)","Efficiency Change (EC)","Technical Change (TC)","MPI","Interpretation"]
        ws.write_row(2,0,headers,st["header"]); ws.freeze_panes(3,3); ws.autofilter(2,0,2+len(result["malmquist_rows"]),len(headers)-1)
        for r,row in enumerate(result["malmquist_rows"],start=3):
            vals=[row["DMU_ID"],row["Period_t"],row["Period_t1"],row["D_t(x_t,y_t)"],row["D_t(x_t1,y_t1)"],row["D_t1(x_t,y_t)"],row["D_t1(x_t1,y_t1)"]]
            ws.write_row(r,0,vals)
            ws.write_formula(r,7,f"=G{r+1}/D{r+1}",st["num"],row["EC"])
            ws.write_formula(r,9,f"=SQRT((E{r+1}/D{r+1})*(G{r+1}/F{r+1}))",st["num"],row["MPI"])
            ws.write_formula(r,8,f"=J{r+1}/H{r+1}",st["num"],row["TC"])
            ws.write_formula(r,10,f'=IF(J{r+1}>1,"Productivity improved",IF(J{r+1}<1,"Productivity declined","No change"))',None,row["Interpretation"])
        for col,width in enumerate([18,14,14,18,21,20,22,22,22,15,27]): ws.set_column(col,col,width)
    elif model == "CrossEfficiency":
        ws=wb.add_worksheet("Cross_Efficiency"); _sheet_base(ws,"Cross-Efficiency Matrix","Rows are evaluating DMUs; columns are peer DMUs scored with each row DMU's CCR multiplier weights.",st)
        names=result["names"]; ws.write_row(2,0,["Evaluator \\ Evaluated",*names,"Aggregate score"],st["header"])
        for i,nm in enumerate(names):
            row=3+i; ws.write(row,0,nm)
            for j in range(len(names)):
                value=float(result["cross_matrix"][i,j])
                if np.isfinite(value): ws.write_number(row,1+j,value,st["num"])
                else: ws.write(row,1+j,"N/A")
            # Aggregate each evaluated DMU's column across all evaluator rows.
            # The matrix is evaluator-by-evaluated, so a horizontal average
            # would summarize one evaluator instead of one evaluated DMU.
            aggregate_col=xlsxwriter.utility.xl_col_to_name(i+1)
            first_evaluator_row=4
            last_evaluator_row=3+len(names)
            if str(input_bundle["config"].get("CrossEfficiency_Aggregation","Mean")).lower()=="median":
                formula=f"=MEDIAN({aggregate_col}${first_evaluator_row}:{aggregate_col}${last_evaluator_row})"
            else:
                formula=f"=AVERAGE({aggregate_col}${first_evaluator_row}:{aggregate_col}${last_evaluator_row})"
            agg=float(result["cross_aggregate"][i])
            if np.isfinite(agg): ws.write_formula(row,1+len(names),formula,st["num"],agg)
            else: ws.write(row,1+len(names),"N/A")
        ws.write(2,1+len(names)+2,"Aggregate method",st["section"]); ws.write(3,1+len(names)+2,input_bundle["config"].get("CrossEfficiency_Aggregation","Mean"))
        ws.set_column(0,0,24); ws.set_column(1,len(names)+1,15)
        wws=wb.add_worksheet("Cross_Weights"); _sheet_base(wws,"Multiplier Weights","One optimal CCR multiplier vector is used per evaluating DMU. Alternative optimal weights may exist.",st)
        wws.write_row(2,0,["Evaluator DMU","Weight type","Variable","Weight"],st["header"]); rr=3
        for i,nm in enumerate(names):
            u,v=result["cross_weights"][i]
            for c,val in zip(input_bundle["input_cols"],v): wws.write_row(rr,0,[nm,"Input",c,float(val)]); rr+=1
            for c,val in zip(input_bundle["output_cols"],u): wws.write_row(rr,0,[nm,"Output",c,float(val)]); rr+=1
        wws.set_column("A:A",22); wws.set_column("B:B",16); wws.set_column("C:C",26); wws.set_column("D:D",16)
    else:
        results=result["results"]; score_ws=wb.add_worksheet("Scores")
        _sheet_base(score_ws,"DEA Efficiency Scores","Scores are obtained by solving the selected linear/fractional program; score formulas and solver settings are documented in Formula_Audit.",st)
        headers=["DMU_ID","Period","Model","Orientation","RTS","Efficiency / Slack Score","Radial Factor","CRS Efficiency","VRS Efficiency","Scale Efficiency","Status","Score Formula"]
        score_ws.write_row(2,0,headers,st["header"]); score_ws.autofilter(2,0,2+len(results),len(headers)-1)
        for r,res in enumerate(results,start=3):
            score_ws.write_row(r,0,[res.dmu,res.period,res.model,res.orientation,res.rts])
            if res.radial_factor is None:
                score_ws.write_number(r,5,res.score,st["num"]); score_ws.write_blank(r,6,None)
                ftext="SBM: optimized rho" if res.model=="SBM" else "Additive: normalized sum of input/output slacks"
            elif res.orientation=="Output":
                score_ws.write_formula(r,5,f"=1/G{r+1}",st["num"],res.score); score_ws.write_number(r,6,res.radial_factor,st["num"])
                ftext="Efficiency = 1 / phi* (output-oriented)"
            else:
                score_ws.write_formula(r,5,f"=G{r+1}",st["num"],res.score); score_ws.write_number(r,6,res.radial_factor,st["num"])
                ftext="Efficiency = theta* (input-oriented)"
            if res.crs_score is not None:
                score_ws.write_number(r,7,res.crs_score,st["num"]); score_ws.write_number(r,8,res.vrs_score,st["num"])
                score_ws.write_formula(r,9,f"=H{r+1}/I{r+1}",st["num"],res.scale_efficiency)
            score_ws.write(r,10,res.status); score_ws.write(r,11,ftext)
        for c,width in enumerate([20,14,20,16,12,25,18,18,18,18,24,44]): score_ws.set_column(c,c,width)

        target_ws=wb.add_worksheet("Targets"); _sheet_base(target_ws,"Peer Projections and Targets","Projected values are weighted sums of peer observations; improvement is actual minus target for inputs and target minus actual for outputs.",st)
        target_ws.write_row(2,0,["DMU_ID","Period","Variable","Type","Actual","Projected Target","Improvement","Improvement %"],st["header"])
        raw=input_bundle["data"].set_index(["DMU_ID","Period"])
        rr=3
        for res in results:
            for typ,cols,tmap in [("Input",input_bundle["input_cols"],res.input_targets),("Output",input_bundle["output_cols"],res.output_targets)]:
                for col in cols:
                    actual=float(raw.loc[(res.dmu,res.period),col]); target=float(tmap[col]); row=rr
                    target_ws.write_row(row,0,[res.dmu,res.period,col,typ,actual,target])
                    if typ=="Input": target_ws.write_formula(row,6,f"=E{row+1}-F{row+1}",st["num"],actual-target)
                    else: target_ws.write_formula(row,6,f"=F{row+1}-E{row+1}",st["num"],target-actual)
                    target_ws.write_formula(row,7,f'=IF(E{row+1}=0,"",G{row+1}/E{row+1})',st["pct"],(actual-target)/actual if typ=="Input" and actual else ((target-actual)/actual if actual else ""))
                    rr+=1
        for c,width in enumerate([20,14,25,16,18,20,19,18]): target_ws.set_column(c,c,width)

        peer_ws=wb.add_worksheet("Peer_Weights"); _sheet_base(peer_ws,"Reference Set and Lambda Weights","Positive lambda values identify peer DMUs used to construct the projection.",st)
        peer_ws.write_row(2,0,["Evaluated DMU","Period","Peer DMU","Lambda"],st["header"]); rr=3
        for res in results:
            for peer,lam in res.lambdas.items(): peer_ws.write_row(rr,0,[res.dmu,res.period,peer,lam]); rr+=1
        peer_ws.set_column("A:C",22); peer_ws.set_column("D:D",18)

        slack_ws=wb.add_worksheet("Slacks"); _sheet_base(slack_ws,"Input and Output Slacks","Slacks are residual improvements after the radial adjustment (or the model-native non-radial solution).",st)
        slack_ws.write_row(2,0,["DMU_ID","Period","Variable","Type","Slack"],st["header"]); rr=3
        for res in results:
            for typ,mapping in [("Input",res.input_slacks),("Output",res.output_slacks)]:
                for var,value in mapping.items(): slack_ws.write_row(rr,0,[res.dmu,res.period,var,typ,value]); rr+=1
        slack_ws.set_column("A:A",20); slack_ws.set_column("B:B",14); slack_ws.set_column("C:C",25); slack_ws.set_column("D:D",15); slack_ws.set_column("E:E",18)

        check_ws=wb.add_worksheet("Constraint_Checks"); _sheet_base(check_ws,"DEA Constraint Checks","Residuals should be close to zero within the configured solver tolerance. LHS/RHS values expose the solved envelopment equalities.",st)
        check_ws.write_row(2,0,["DMU_ID","Period","Constraint","Variable","Peer Projection","Slack-adjusted LHS","RHS","Residual"],st["header"])
        raw=input_bundle["data"].set_index(["DMU_ID","Period"]); rr=3
        for res in results:
            for var in input_bundle["input_cols"]:
                actual=float(raw.loc[(res.dmu,res.period),var]); proj=res.input_targets[var]; slack=res.input_slacks[var]
                rhs=(res.radial_factor*actual if res.radial_factor is not None and res.orientation=="Input" else actual)
                lhs=proj+slack
                check_ws.write_row(rr,0,[res.dmu,res.period,"Input constraint",var,proj,lhs,rhs])
                check_ws.write_formula(rr,7,f"=F{rr+1}-G{rr+1}",st["num"],lhs-rhs); rr+=1
            for var in input_bundle["output_cols"]:
                actual=float(raw.loc[(res.dmu,res.period),var]); proj=res.output_targets[var]; slack=res.output_slacks[var]
                rhs=(res.radial_factor*actual if res.radial_factor is not None and res.orientation=="Output" else actual)
                lhs=proj-slack
                check_ws.write_row(rr,0,[res.dmu,res.period,"Output constraint",var,proj,lhs,rhs])
                check_ws.write_formula(rr,7,f"=F{rr+1}-G{rr+1}",st["num"],lhs-rhs); rr+=1
        for c,width in enumerate([20,14,22,25,20,22,20,18]): check_ws.set_column(c,c,width)

    audit=wb.add_worksheet("Formula_Audit"); _sheet_base(audit,"Model Formulation and Calculation Audit","This sheet documents the mathematical program and score convention applied to the imported data.",st)
    audit.set_column("A:A",30); audit.set_column("B:B",110)
    formulas=[
        ("Model family",model),("Orientation",orientation),("Returns to scale",rts),
        ("Efficiency frontier", "A DEA score of 1 indicates the estimated frontier under radial CCR/BCC. SBM uses rho; additive uses normalized slack objective."),
        ("Peer weights", "For each evaluated DMU o, lambda_j >= 0 weights reference DMUs. The projected bundle is X'lambda and Y'lambda."),
        ("Input-oriented radial LP", "min theta; X'lambda <= theta*x_o; Y'lambda >= y_o; lambda >= 0. Under VRS add sum(lambda)=1. Efficiency score = theta*; 0 < theta* <= 1."),
        ("Output-oriented radial LP", "max phi; X'lambda <= x_o; Y'lambda >= phi*y_o; lambda >= 0. Under VRS add sum(lambda)=1. Reported efficiency score = 1/phi*."),
        ("Input slacks", "For input orientation: X'lambda + s- = theta*x_o; Y'lambda - s+ = y_o. For output orientation: X'lambda + s- = x_o; Y'lambda - s+ = phi*y_o."),
        ("BCC returns to scale", "sum(lambda)=1 (VRS). CCR uses CRS with no convexity restriction. NIRS adds sum(lambda)<=1; NDRS adds sum(lambda)>=1."),
        ("Scale efficiency", "When both CRS and VRS radial models are solved with matching orientation, Scale Efficiency = CRS technical efficiency / VRS technical efficiency."),
        ("SBM objective", "Input-oriented SBM: rho = [1 - (1/m) sum_i(s_i-/x_io)] / [1 + (1/s) sum_r(s_r+/y_ro)], minimized subject to the envelopment equalities and selected returns-to-scale condition."),
        ("Additive objective", "Maximize the sum of input and output slacks normalized by each variable's observed maximum. This composite is scale-dependent by design and is not compared to radial efficiency scores."),
        ("Cross-efficiency", "For evaluator k, maximize sum_r(u_r*y_rk) subject to sum_i(v_i*x_ik)=1 and sum_r(u_r*y_rj)-sum_i(v_i*x_ij)<=0 for every peer j. Cross-score(k,j)=(u_k*y_j)/(v_k*x_j)."),
        ("Malmquist MPI", "MPI = sqrt([D_t(x_t+1,y_t+1)/D_t(x_t,y_t)] * [D_t+1(x_t+1,y_t+1)/D_t+1(x_t,y_t)]). EC=D_t+1(x_t+1,y_t+1)/D_t(x_t,y_t); TC=MPI/EC."),
        ("Solver", "Linear programs are solved with SciPy HiGHS. The Excel formulas reproduce score conversions and decompositions; LP optima themselves are solver results, not spreadsheet formula recalculations."),
        ("Input file",input_bundle["source_path"]),
    ]
    audit.write_row(2,0,["Item","Definition / formula"],st["header"])
    for i,(label,text) in enumerate(formulas,start=3): audit.write(i,0,label,st["section"]); audit.write(i,1,str(text),st["formula"])
    for i in range(3,3+len(formulas)): audit.set_row(i,38)

    source=wb.add_worksheet("Input_Data"); _sheet_base(source,"Imported Data","Values copied from the selected Data sheet and used as model inputs.",st)
    data=input_bundle["data"]
    keep=["DMU_ID","Period",*input_bundle["input_cols"],*input_bundle["output_cols"]]
    source.write_row(2,0,keep,st["header"])
    for ri,row in enumerate(data[keep].itertuples(index=False,name=None),start=3):
        source.write_row(ri,0,list(row))
    source.freeze_panes(3,2); source.autofilter(2,0,2+len(data),len(keep)-1)
    source.set_column(0,0,20); source.set_column(1,1,14); source.set_column(2,len(keep)-1,18)
    wb.set_properties({"title":"DEA Analysis Results","subject":"Auditable Data Envelopment Analysis output","author":"DEA Desktop Tool"})
    wb.close()
    return output_path
