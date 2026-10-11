import tempfile
import unittest
from pathlib import Path

import numpy as np
from openpyxl import load_workbook

from MCDMStudio.core.excel_io import DEMATEL_DEMO, DEMATEL_TEMPLATE, DEMO, TEMPLATE, generate_template, load_input, method_input_preview, save_edited_input, save_workbook_edits, write_results
from MCDMStudio.core.methods import calculate_ahp, calculate_swara, run_ranking

class MCDMMethodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_input(DEMO)

    def test_demo_workbook_loads(self):
        self.assertEqual(self.data['matrix'].shape,(4,4))
        self.assertEqual(len(self.data['criteria']),4)
        self.assertEqual(set(self.data['directions']),{'Benefit','Cost'})
        self.assertTrue({'Instructions','Method Guide','Decision Matrix','Criteria','AHP Pairwise','SWARA'} <= set(self.data['sheet_previews']))
        self.assertEqual(len(self.data['sheet_previews']['AHP Pairwise']),4)

    def test_two_workbook_shapes_and_edit_save_roundtrip(self):
        topsis=load_input(DEMO); dematel=load_input(DEMATEL_DEMO)
        self.assertEqual(topsis['decision_mode'],'TOPSIS'); self.assertEqual(topsis['preview'].columns[0],'Alternative')
        self.assertEqual(dematel['decision_mode'],'DEMATEL'); self.assertEqual(dematel['preview'].columns[0],'Factor')
        self.assertIn('DEMATEL Direct Relations',dematel['sheet_previews'])
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'reviewed.xlsx'
            edit=topsis['preview'].copy(); edit.iloc[0,1]=123.0
            save_edited_input(DEMO,out,edit,'TOPSIS')
            self.assertEqual(load_input(out)['matrix'][0,0],123.0)
            out2=Path(temp)/'dematel.xlsx'; edit2=dematel['preview'].copy(); edit2.iloc[0,1]=3.0
            save_edited_input(DEMATEL_DEMO,out2,edit2,'DEMATEL')
            self.assertEqual(load_input(out2)['dematel'][0,0],3.0)

    def test_first_step_uses_selected_methods_input_sheet(self):
        data=load_input(DEMO)
        dematel_input=method_input_preview(data,'DEMATEL')
        self.assertEqual(dematel_input.columns[0],'Factor')
        self.assertEqual(dematel_input.iloc[0,0],'F1')
        self.assertEqual(method_input_preview(data,'AHP').columns[0],'Criterion')
        self.assertEqual(method_input_preview(data,'TOPSIS').columns[0],'Alternative')

    def test_generated_templates_have_distinct_layouts_and_input_colors(self):
        with tempfile.TemporaryDirectory() as temp:
            t=Path(temp)/'topsis.xlsx'; d=Path(temp)/'dematel.xlsx'
            generate_template(t,False,'TOPSIS'); generate_template(d,False,'DEMATEL')
            tw=load_workbook(t); dw=load_workbook(d)
            self.assertIn('Decision Matrix',tw.sheetnames); self.assertIn('DEMATEL Direct Relations',dw.sheetnames)
            self.assertEqual(tw['Decision Matrix']['B2'].fill.fgColor.rgb[-6:],'FFF2C6')
            self.assertEqual(dw['DEMATEL Direct Relations']['B2'].fill.fgColor.rgb[-6:],'D8E1E8')
            self.assertIn('Method Guide',tw.sheetnames); self.assertIn('Method Guide',dw.sheetnames)
            mappings={row[0].value:row[1].value for row in tw['Method Guide'].iter_rows(min_row=2)}
            self.assertIn('TOPSIS',mappings['Decision Matrix']); self.assertIn('DEMATEL',mappings['DEMATEL Direct Relations'])
            self.assertTrue(tw['AHP Pairwise']['A1'].comment)

    def test_all_sheet_editor_saves_values_and_headers(self):
        data=load_input(DEMO)
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'edited.xlsx'
            criteria=data['sheet_previews']['Criteria'].copy()
            criteria.iloc[0,1]='Cost'
            criteria.columns=['Criterion','Preference','Manual weight','BWM best?','BWM worst?','Best-to-criterion','Criterion-to-worst']
            matrix=data['sheet_previews']['Decision Matrix'].copy(); matrix.iloc[0,1]=123
            save_workbook_edits(DEMO,out,{'Criteria':criteria,'Decision Matrix':matrix})
            wb=load_workbook(out,data_only=True)
            self.assertEqual(wb['Criteria']['B1'].value,'Preference')
            self.assertEqual(wb['Criteria']['B2'].value,'Cost')
            self.assertEqual(wb['Decision Matrix']['B2'].value,123)

    def test_ahp_weights_are_normalized_and_consistent(self):
        weights, steps=calculate_ahp(self.data['criteria'],self.data['ahp'])
        self.assertAlmostEqual(float(weights.sum()),1.0,places=10)
        self.assertLess(float(steps[-1].table.iloc[0]['CR']),.1)

    def test_ahp_rejects_nonreciprocal_matrix(self):
        matrix=self.data['ahp'].copy(); matrix[0,1]=5
        with self.assertRaisesRegex(ValueError,'reciprocal'):
            calculate_ahp(self.data['criteria'],matrix)

    def test_swara_weights_are_normalized(self):
        weights, steps=calculate_swara(self.data['criteria'],self.data['swara'])
        self.assertAlmostEqual(float(weights.sum()),1.0,places=10)
        self.assertIn('Weight',steps[-1].table.columns)

    def test_cost_direction_in_saw(self):
        steps=run_ranking('SAW',[[10,1],[10,10]],['low cost','high cost'],['Benefit','Cost'],['Benefit','Cost'],[.5,.5])
        self.assertEqual(steps[-1].table.iloc[0]['Alternative'],'low cost')

    def test_every_ranking_method_returns_stepwise_tables(self):
        for method in ['SAW','TOPSIS','MOORA','COPRAS-G','ARAS','WASPAS','VIKOR']:
            with self.subTest(method=method):
                steps=run_ranking(method,self.data['matrix'],self.data['alternatives'],self.data['criteria'],self.data['directions'],self.data['weights'])
                self.assertGreaterEqual(len(steps),3)
                self.assertTrue(all(step.title and step.formula and step.book_ref for step in steps))
                self.assertGreaterEqual(len(steps[-1].table),2)
        moora=run_ranking('MOORA',self.data['matrix'],self.data['alternatives'],self.data['criteria'],self.data['directions'],self.data['weights'])[-1].table
        self.assertIn('Alternative',moora.columns)
        self.assertIn('Rank',moora.columns)

    def test_export_creates_one_sheet_per_step(self):
        steps=run_ranking('TOPSIS',self.data['matrix'],self.data['alternatives'],self.data['criteria'],self.data['directions'],self.data['weights'])
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'steps.xlsx'; write_results(out,'TOPSIS',self.data,self.data['weights'],steps)
            sheets=load_workbook(out,read_only=True).sheetnames
            self.assertEqual(len(sheets),len(steps)+3)
            self.assertIn('Summary',sheets); self.assertIn('Input Matrix',sheets)

if __name__=='__main__': unittest.main()
