from __future__ import annotations

import re
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
VBA_ROOT = ROOT / "VBAFUZZY_ONL"


def convert_latex_to_word(text: str) -> str:
    """Convert common LaTeX math tokens to Word's linear equation syntax."""
    value = text.strip().replace(r"\left", "").replace(r"\right", "")
    value = value.replace(r"\cdot", "·").replace(r"\times", "×")
    value = value.replace(r"\leq", "≤").replace(r"\geq", "≥").replace(r"\neq", "≠")
    value = value.replace(r"\mu", "μ").replace(r"\nu", "ν").replace(r"\pi", "π")
    value = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", value)
    value = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", value)
    value = re.sub(r"\\(?:mathrm|text)\{([^{}]+)\}", r"\1", value)
    return value


def convert_word_to_latex(text: str) -> str:
    """Convert common Word linear math notation to readable LaTeX source."""
    value = text.strip().replace("×", r"\times ").replace("·", r"\cdot ")
    value = value.replace("≤", r"\leq ").replace("≥", r"\geq ").replace("≠", r"\neq ")
    value = value.replace("μ", r"\mu ").replace("ν", r"\nu ").replace("π", r"\pi ")
    value = re.sub(r"√\(([^()]+)\)", lambda m: r"\sqrt{" + m.group(1) + "}", value)
    value = re.sub(r"\(([^()]+)\)/\(([^()]+)\)", lambda m: r"\frac{" + m.group(1) + "}{" + m.group(2) + "}", value)
    return value


class FuzzyStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FuzzyStudio")
        self.geometry("1180x790")
        self.minsize(900, 640)
        self.configure(bg="#F3F5FA")
        style = ttk.Style(self); style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#F3F5FA", foreground="#172033")
        style.configure("TNotebook", background="#F3F5FA", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(13, 8), background="#E7ECF4")
        style.map("TNotebook.Tab", background=[("selected", "#17365D")], foreground=[("selected", "white")])
        style.configure("TButton", padding=(10, 7))
        header = tk.Frame(self, bg="#0F172A"); header.pack(fill="x")
        tk.Label(header, text="FuzzyStudio", bg="#0F172A", fg="white", font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=19, pady=(8, 1))
        tk.Label(header, text="Fuzzy operations · VBA reference · Equation conversion", bg="#0F172A", fg="#C7D2FE", font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 8))
        tk.Button(header,text="Open Templates",command=self.open_templates_folder,bg="#1E293B",fg="white",activebackground="#334155",activeforeground="white",relief="flat",padx=10,pady=5).pack(side="right",padx=18)
        self.tabs = ttk.Notebook(self); self.tabs.pack(fill="both", expand=True, padx=14, pady=7)
        self.build_type_tab("Spherical Fuzzy", "tools_spherical/main.py", "SPF tuples use (membership; non-membership; hesitancy). The included tool also provides weighted aggregation and Excel import.")
        self.build_type_tab("Quantum Spherical", "tools_quantum/main.py", "QFS/QSFS values use the notation expected by the source parser. Use the original tool's examples and workbook templates for valid input strings.")
        self.build_type_tab("Neutrosophic Z", "tools_neutrosophic/main.py", "Neutrosophic Z-number operations and weighted aggregation. The included tool provides examples and templates for its expected tuple syntax.")
        self.build_vba_tab()
        self.build_converter_tab()

    def build_type_tab(self, title, rel_entry, description):
        page = ttk.Frame(self.tabs, padding=22); self.tabs.add(page, text=title)
        ttk.Label(page, text=title, font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(5, 8))
        ttk.Label(page, text=description, wraplength=1000, justify="left").pack(anchor="w", pady=(0, 20))
        if rel_entry:
            ttk.Label(page, text="This opens the original calculator window so its existing operations, batch aggregation, formulas and workbook handling stay available.", wraplength=980, justify="left").pack(anchor="w", pady=6)
            ttk.Button(page, text="Open calculator", command=lambda p=ROOT / rel_entry: self.launch(p)).pack(anchor="w", pady=12)
        else:
            ttk.Label(page, text="This package's additional fuzzy types are represented in the VBA library. The source files remain organized in their original method folders.", wraplength=980, justify="left").pack(anchor="w", pady=6)
            ttk.Button(page, text="Open VBA Guide", command=lambda: self.tabs.select(self.vba_tab)).pack(anchor="w", pady=12)

    def launch(self, entry):
        if not entry.exists():
            messagebox.showerror("Calculator unavailable", f"Missing app entry point:\n{entry}"); return
        try:
            if getattr(sys, "frozen", False):
                tool = {"tools_spherical": "SphericalFuzzy.exe", "tools_quantum": "QuantumSpherical.exe", "tools_neutrosophic": "NeutrosophicZ.exe"}.get(entry.parent.name)
                executable = Path(sys.executable).parent / tool if tool else None
                if executable is None or not executable.exists():
                    raise FileNotFoundError("The calculator executable is missing from the FuzzyStudio folder. Run build_all_windows.bat again.")
                subprocess.Popen([str(executable)], cwd=str(executable.parent))
            else:
                subprocess.Popen([sys.executable, str(entry)], cwd=str(entry.parent))
        except Exception as exc:
            messagebox.showerror("Could not start calculator", str(exc))

    def open_templates_folder(self):
        folder = (Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT.parent) / "Templates"
        if not folder.exists():
            messagebox.showerror("Templates unavailable", f"Extract the shared Templates folder beside the app.\n\n{folder}"); return
        try:
            if hasattr(os, "startfile"): os.startfile(str(folder))
            elif sys.platform == "darwin": subprocess.Popen(["open", str(folder)])
            else: subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc: messagebox.showerror("Could not open Templates", str(exc))

    def copy_vba_source(self):
        source = getattr(self, "_current_source", "")
        if not source:
            messagebox.showinfo("No VBA code selected", "Select a module or procedure in VBA Guide first."); return
        try:
            self.clipboard_clear(); self.clipboard_append(source); self.update()
        except tk.TclError as exc:
            messagebox.showerror("Copy failed", f"Could not copy the displayed VBA source.\n\n{exc}")

    def export_vba_text(self):
        source = getattr(self, "_current_source", "")
        if not source:
            messagebox.showinfo("No VBA code selected", "Select a module or procedure in VBA Guide first."); return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text file", "*.txt")], initialfile="VBA_Code.txt")
        if path:
            try: Path(path).write_text(source.rstrip() + "\n", encoding="utf-8-sig")
            except OSError as exc: messagebox.showerror("Export failed", str(exc))

    def export_vba_bas(self):
        source_path = getattr(self, "_current_module_path", None)
        if not source_path:
            messagebox.showinfo("No VBA module selected", "Select a module or procedure in VBA Guide first."); return
        path = filedialog.asksaveasfilename(defaultextension=".bas", filetypes=[("VBA module", "*.bas")], initialfile=source_path.name)
        if path:
            try: shutil.copyfile(source_path, path)
            except OSError as exc: messagebox.showerror("Export failed", str(exc))

    def open_vba_library(self):
        library = (Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT) / "VBA Library"
        library.mkdir(exist_ok=True)
        try:
            if hasattr(os, "startfile"): os.startfile(str(library))
            elif sys.platform == "darwin": subprocess.Popen(["open", str(library)])
            else: subprocess.Popen(["xdg-open", str(library)])
        except Exception as exc: messagebox.showerror("Could not open VBA Library", f"Folder: {library}\n\n{exc}")

    def build_vba_tab(self):
        page = ttk.Frame(self.tabs, padding=16); self.vba_tab = page; self.tabs.add(page, text="VBA Guide")
        ttk.Label(page, text="VBA function and procedure guide", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(page, text="Pick a module or function to see its purpose, arguments, dependencies, examples and procedure settings. Select an item to show its actual source in the separate VBA Code tab.", wraplength=1050, justify="left").pack(anchor="w", pady=(0, 8))
        controls = ttk.Frame(page); controls.pack(fill="x", pady=4)
        search_var=tk.StringVar();ttk.Label(controls,text="Filter functions / modules").pack(side="left");ttk.Entry(controls,textvariable=search_var,width=42).pack(side="left",padx=8)
        split=ttk.Panedwindow(page,orient="horizontal");split.pack(fill="both",expand=True,pady=7)
        left=ttk.Frame(split);right=ttk.Frame(split);split.add(left,weight=2);split.add(right,weight=3)
        tree=ttk.Treeview(left,columns=("kind",),show="tree headings");tree.heading("#0",text="VBA module / member");tree.heading("kind",text="Type");tree.column("kind",width=80,stretch=False)
        ys=ttk.Scrollbar(left,orient="vertical",command=tree.yview);tree.configure(yscrollcommand=ys.set);tree.pack(side="left",fill="both",expand=True);ys.pack(side="right",fill="y")
        detail=tk.Text(right,wrap="word",height=24,font=("Segoe UI",10),bg="white",relief="flat",padx=12,pady=10);detail.pack(fill="both",expand=True)
        code_page=ttk.Frame(self.tabs,padding=12);self.vba_code_tab=code_page;self.tabs.add(code_page,text="VBA Code")
        self.code_title=tk.StringVar(value="Select a module or function in VBA Guide")
        ttk.Label(code_page,textvariable=self.code_title,font=("Segoe UI",13,"bold")).pack(anchor="w",pady=(0,6))
        ttk.Label(code_page,text="The selected procedure is shown by itself; selecting a module shows the complete .bas source. Copy or export the visible procedure, or export the complete module for Excel.",style="Muted.TLabel",wraplength=1050).pack(anchor="w",pady=(0,6))
        self._current_source="";self._current_module_path=None
        code_actions=ttk.Frame(code_page);code_actions.pack(fill="x",pady=(0,6))
        ttk.Button(code_actions,text="Copy displayed code",command=self.copy_vba_source).pack(side="left",padx=(0,6))
        ttk.Button(code_actions,text="Export displayed code .txt…",command=self.export_vba_text).pack(side="left",padx=6)
        ttk.Button(code_actions,text="Export full module .bas…",command=self.export_vba_bas).pack(side="left",padx=6)
        ttk.Button(code_actions,text="Open VBA Library folder",command=self.open_vba_library).pack(side="right",padx=4)
        self.code_text=tk.Text(code_page,wrap="none",font=("Consolas",10),bg="#111827",fg="#E5E7EB",insertbackground="white",padx=10,pady=8)
        cy=ttk.Scrollbar(code_page,orient="vertical",command=self.code_text.yview);cx=ttk.Scrollbar(code_page,orient="horizontal",command=self.code_text.xview);self.code_text.configure(yscrollcommand=cy.set,xscrollcommand=cx.set)
        self.code_text.pack(side="left",fill="both",expand=True);cy.pack(side="right",fill="y");cx.pack(side="bottom",fill="x")
        pattern=re.compile(r"^\s*(Function|Sub)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\([^\r\n]*\))?",re.I)
        records=[];modules={}
        for file in sorted(VBA_ROOT.rglob("*.bas")):
            rel=file.relative_to(VBA_ROOT).as_posix()
            try:lines=file.read_text(encoding="utf-8-sig",errors="replace").splitlines()
            except OSError:continue
            modules[file]=(rel,lines)
            for n,line in enumerate(lines,1):
                m=pattern.match(line)
                if m:records.append((rel,m.group(1).title(),m.group(2),m.group(3) or "()",n,file,line.strip()))

        def procedure(lines,start):
            head=pattern.match(lines[start-1]);endword="End Function" if head and head.group(1).lower()=="function" else "End Sub"
            end=start
            while end<len(lines) and lines[end].strip().lower()!=endword.lower():end+=1
            return lines[start-1:end+1],end+1

        def explanation(rel,name,kind,args,body):
            low=rel.lower();upper=name.upper();src="\n".join(body);calls=sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(",src)))
            intrinsics={"IF","MID","LEFT","RIGHT","LEN","ROUND","CDBL","TRIM","SPLIT","INSTR","ABS","SQRT","EXP","LOG","WORKSHEETFUNCTION","CELLS","RANGE","SHEETS","MAX","MIN","SUM","AVERAGE"}
            deps=[c for c in calls if c.upper() not in intrinsics and c.upper()!=upper]
            if kind=="Sub":
                purpose="Workbook macro. This is a procedure, not a worksheet formula; it reads and writes worksheet cells."
                config=[]
                for line in body:
                    m=re.match(r"\s*(num_row|num_col|num_exp|exp_row_offset|exp_col_offset|agg_row_offset|agg_col_offset|exp_code)\s*=\s*(.+)",line,re.I)
                    if m:config.append(f"{m.group(1)} = {m.group(2).strip()}")
                if config:purpose += "\n\nSettings found in this Sub:\n"+"\n".join(config)
                example=f"Run {name} from Developer → Macros only after matching sheet names and matrix coordinates to the settings above. The macro writes into worksheets."
            elif kind=="Function" and any(x in upper for x in ("SWAM","PWFA","WAA")):
                purpose="Weighted arithmetic aggregation: the implementation applies each weight as a scalar coefficient, then combines those fuzzy values with the family’s fuzzy addition rule. This description is based on the coefficient/addition calls in the source."
                example=f"Worksheet formula: ={name}(A2:A4,B2:B4). Put fuzzy tuples in the first range and matching numeric weights in the second; keep both ranges the same size."
            elif kind=="Function" and upper in {"WGAOBC1"}:
                purpose="Unweighted geometric aggregation: the function repeatedly combines the fuzzy values using the module’s MULBC operation. Its signature has one input and the source does not apply a weight range."
                example=f"Worksheet formula: ={name}(A2:A4), where the range contains fuzzy values. No weights argument is declared."
            elif kind=="Function" and any(x in upper for x in ("SWGM","SWAG","PWFG","WGA")):
                purpose="Weighted geometric aggregation: the source applies a power operation using each weight, then combines the weighted fuzzy values with the family’s multiplication rule."
                example=f"Worksheet formula: ={name}(A2:A4,B2:B4). Put fuzzy tuples in the first range and aligned numeric weights in the second; keep both ranges the same size."
            elif kind=="Function" and "AGGW" in upper:
                purpose="Weighted aggregate over the first input, with the second input providing weights. The exact fuzzy component formula is implemented directly in this function."
                example=f"Use ={name}(fuzzy_values,weights), following the declared parameter types and aligning each weight with one fuzzy value."
            elif kind=="Function" and "AGG" in upper:
                purpose="Unweighted aggregate over the provided fuzzy values. The function’s source applies its method-specific component formula without a separate weight input."
                example=f"Use ={name}(fuzzy_values_range), following the declared parameter type."
            elif upper in {"GET_A","GET_B","GET_Y","GET_POS","GET_NAU","GET_NEG","QFSUC","QFSUE","QFSVC","QFSVE","QFSHC","QFSHE"}:
                if upper in {"GET_A","GET_POS","QFSUC","QFSUE"}:piece="reads the first component/encoded pair from the tuple string"
                elif upper in {"GET_B","GET_NAU","QFSVC","QFSVE"}:piece="finds the next semicolon-delimited component and reads its value/encoded pair"
                else:piece="reads the final component/encoded pair after the second delimiter"
                purpose=f"Tuple parser helper: {name} {piece}. It converts the extracted text to a number; several helpers round to a fixed number of decimal places."
                sample='"(0.60; 0.20; 0.30)"' if "QFS" not in upper else '"(0.4ej2p0.4; 0.3ej2p0.2; 0.8ej2p0.3)"'
                example=f"Example pattern: ={name}({sample}). Check the tuple syntax expected by this family's parser."
            elif any(x in upper for x in ("SUM","ADD")):
                purpose=f"Fuzzy addition operator. {name} reads components from its fuzzy input argument(s), applies the family's sum formula and returns a formatted fuzzy tuple."
                example=f"Example pattern: ={name}(A2,B2), with A2 and B2 containing fuzzy tuples in the format used by this module."
            elif "MUL" in upper:
                purpose=f"Fuzzy multiplication operator. {name} combines two fuzzy values using the component-wise multiplication formula in the body."
                example=f"Example pattern: ={name}(A2,B2), with two cells containing valid fuzzy tuples."
            elif "COE" in upper:
                purpose=f"Scalar coefficient operation. {name} applies the numeric coefficient in its second argument to a fuzzy value and returns a fuzzy tuple."
                example=f"Example pattern: ={name}(A2,0.5). The second argument is a numeric coefficient."
            elif "POW" in upper:
                purpose=f"Power operation. {name} raises/transforms a fuzzy value according to the exponent in its second argument."
                example=f"Example pattern: ={name}(A2,2). The second argument is a numeric exponent."
            elif "DEF" in upper or "SCORE" in upper or "DIS" in upper:
                purpose=f"Produces a crisp score/defuzzified value (or distance) from fuzzy input. Inspect the displayed procedure for the exact expression."
                example=f"Example pattern: ={name}(A2), where A2 contains one valid fuzzy tuple."
            else:
                purpose=f"{name} is a {kind.lower()} in {Path(rel).name}. The explanation below is inferred from the operations and calls in its implementation; inspect the source before using it in a research workbook."
                example=f"Declaration: {name}{args}. Follow each parameter's declared type and the example values documented in the module."
            # Check for a likely return-name typo in VBA functions.
            if kind=="Function":
                assigned=set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=",src,re.M|re.I))
                if assigned and not any(x.casefold()==name.casefold() for x in assigned):
                    purpose += f"\n\nCode warning: this Function does not assign a value to its own name ({name}); the source assigns to {', '.join(sorted(assigned))}. This may be a defect and should be verified before relying on its return value."
            if deps:purpose += "\n\nCalls other VBA functions: "+", ".join(deps)+". Import their modules too."
            return purpose,example

        def populate(*_):
            tree.delete(*tree.get_children());parents={};filt=search_var.get().strip().lower()
            for rel,kind,name,args,n,path,line in records:
                if filt and filt not in f"{rel} {name} {line}".lower():continue
                parent=parents.get(rel)
                if parent is None:parent=tree.insert("","end",text=rel,values=("Module",),tags=(str(path),"module"),open=False);parents[rel]=parent
                tree.insert(parent,"end",text=f"{name}{args}",values=(kind,),tags=(str(path),str(n)))
        def show_source(path,start=None,end=None):
            rel,lines=modules[path]
            source="\n".join(lines) if start is None else "\n".join(lines[start-1:end or start])
            self.code_title.set(f"{rel} — full module" if start is None else f"{rel} — selected procedure (line {start})")
            self._current_source=source;self._current_module_path=path
            self.code_text.configure(state="normal");self.code_text.delete("1.0","end");self.code_text.insert("1.0",source);self.code_text.configure(state="disabled")
        def selected(_event=None):
            sel=tree.selection()
            if not sel:return
            item=tree.item(sel[0]);tags=item.get("tags",())
            if not tags:return
            path=Path(tags[0]);rel,lines=modules[path]
            if len(tags)>1 and tags[1]!="module":
                start=int(tags[1]);body,end=procedure(lines,start);m=pattern.match(lines[start-1]);name=m.group(2);kind=m.group(1).title();args=m.group(3) or "()"
                purpose,example=explanation(rel,name,kind,args,body)
                detail.configure(state="normal");detail.delete("1.0","end")
                detail.insert("end",f"{rel}  •  line {start}\n\nDeclaration\n{lines[start-1].strip()}\n\nWhat this code does\n{purpose}\n\nHow to call it\n{example}\n\nVBA setup\n1. Save the workbook as .xlsm.\n2. Press Alt+F11 → File → Import File… and select the .bas module.\n3. Import the dependent modules listed above (for example GetMemberFunction.bas for tuple parsing).\n4. Worksheet Functions are entered as formulas. Subs are run from Developer → Macros and may write to fixed cells.\n")
                detail.configure(state="disabled");show_source(path,start,end)
            else:
                names=[r[2] for r in records if r[5]==path]
                detail.configure(state="normal");detail.delete("1.0","end");detail.insert("end",f"Module: {rel}\n\nDeclared functions / procedures\n"+"\n".join(names)+"\n\nModule purpose\n")
                lower=rel.lower()
                if "getmemberfunction" in lower:purpose="Parses tuple strings and extracts the numeric membership components used by the calculations."
                elif "calculatefunction" in lower:purpose="Implements the fuzzy arithmetic, coefficient/power, score or defuzzification functions."
                elif "aggregatefunction" in lower:purpose="Implements aggregation worksheet functions. SWAM/SWAM-like functions combine weighted fuzzy values by repeated scalar operation plus SUM; SWGM/SWAG functions use power plus MUL."
                elif "aggregateprocedure" in lower:purpose="Contains worksheet macros that copy expert values into work cells, aggregate them, and write results. Its row/column/expert settings are hard-coded in each Sub."
                else:purpose="See the listed member-level explanations and inspect the selected source code."
                detail.insert("end",purpose+"\n\nOpen a member below for its explanation and isolated source code.");detail.configure(state="disabled");show_source(path)
        def view_code():self.tabs.select(self.vba_code_tab)
        search_var.trace_add("write",populate);tree.bind("<<TreeviewSelect>>",selected);populate()
        buttons=ttk.Frame(right);buttons.pack(fill="x",pady=(5,0));ttk.Button(buttons,text="Open selected source →",command=view_code).pack(side="right")
        ttk.Label(page,text=f"Indexed {len(records)} Function/Sub declarations in {len(modules)} .bas modules. Other fuzzy families such as PFS/ProPFS, NEU/NEI, BCLDFN and ISM are searchable here.",style="Muted.TLabel",wraplength=1050).pack(anchor="w",pady=(3,0))

    def build_converter_tab(self):
        page = ttk.Frame(self.tabs, padding=18); self.tabs.add(page, text="LaTeX ↔ Word")
        ttk.Label(page, text="Equation converter", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 5))
        ttk.Label(page, text="Convert common LaTeX math into Word's linear equation input and back. In Word, press Alt+= to insert an equation, then paste the converted linear form.", wraplength=1000).pack(anchor="w", pady=(0, 10))
        self.direction = tk.StringVar(value="LaTeX → Word")
        bar = ttk.Frame(page); bar.pack(fill="x", pady=6)
        ttk.Combobox(bar, textvariable=self.direction, values=["LaTeX → Word", "Word → LaTeX"], state="readonly", width=20).pack(side="left")
        source = tk.Text(page, height=10, wrap="word", font=("Consolas", 11)); source.pack(fill="both", expand=True, pady=6)
        out = tk.Text(page, height=10, wrap="word", font=("Consolas", 11)); out.pack(fill="both", expand=True, pady=6)
        out.configure(state="disabled")
        def convert():
            raw = source.get("1.0", "end").strip()
            value = convert_latex_to_word(raw) if self.direction.get().startswith("LaTeX") else convert_word_to_latex(raw)
            out.configure(state="normal"); out.delete("1.0", "end"); out.insert("1.0", value); out.configure(state="disabled")
        ttk.Button(bar, text="Convert", command=convert).pack(side="left", padx=8)
        ttk.Label(page, text=r"Supported common forms: \frac{a}{b}, \sqrt{x}, powers, Greek μ/ν/π, ×/·, ≤/≥/≠. Nested fractions, matrices and advanced environments need manual review.", wraplength=1000, foreground="#526174").pack(anchor="w", pady=5)


if __name__ == "__main__":
    FuzzyStudio().mainloop()
