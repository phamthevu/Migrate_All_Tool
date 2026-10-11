"""Deterministic randomized and edge-case stress tests for every implemented method."""
import unittest

import numpy as np

from MCDMStudio.core.excel_io import DEMO, load_input
from MCDMStudio.core.methods import (
    RANKING_METHODS, _run_anp, _run_dematel, _run_ism,
    calculate_ahp, calculate_entropy_weights, calculate_swara,
    calculate_bwm_weights,calculate_critic_weights,calculate_merec_weights,calculate_std_weights,calculate_psi_weights,calculate_fucom_weights,
    get_audit_code, run_ranking,
)


class MCDMStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = load_input(DEMO)

    def test_ranking_methods_over_random_matrices(self):
        rng = np.random.default_rng(20261011)
        methods = list(RANKING_METHODS)
        for case in range(40):
            rows = int(rng.integers(2, 16)); cols = int(rng.integers(2, 9))
            x = rng.uniform(0.25, 100, size=(rows, cols))
            dirs = ['Benefit' if j % 2 == 0 else 'Cost' for j in range(cols)]
            weights = rng.uniform(0.05, 1, size=cols); weights /= weights.sum()
            alts = [f'A{i+1}' for i in range(rows)]; crit = [f'C{j+1}' for j in range(cols)]
            for method in methods:
                with self.subTest(case=case, method=method):
                    steps = run_ranking(method, x, alts, crit, dirs, weights)
                    self.assertGreaterEqual(len(steps), 3)
                    for step in steps:
                        self.assertTrue(step.title and step.formula and step.book_ref)
                        numeric = step.table.select_dtypes(include=[np.number]).to_numpy()
                        self.assertTrue(np.isfinite(numeric).all())

    def test_weight_methods_normalize_on_random_inputs(self):
        rng = np.random.default_rng(8)
        for n in range(2, 11):
            criteria = [f'C{i}' for i in range(n)]
            raw = rng.uniform(0.2, 5, size=(n, n)); pairwise = raw / raw.T
            np.fill_diagonal(pairwise, 1)
            w, steps = calculate_ahp(criteria, pairwise)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=10)
            swara = {c: (0 if i == 0 else float(rng.uniform(0, .35))) for i,c in enumerate(criteria)}
            w, _ = calculate_swara(criteria, swara)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=10)
            matrix = rng.uniform(1, 50, size=(n+2, n))
            w, _ = calculate_entropy_weights(criteria, matrix, ['Benefit'] * n)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=10)
            w, _ = calculate_critic_weights(criteria, matrix, ['Benefit'] * n)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=10)
            w, _ = calculate_merec_weights(criteria, matrix, ['Benefit'] * n)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=10)
            w, _ = calculate_std_weights(criteria, matrix, ['Benefit'] * n)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=10)
            w, _ = calculate_psi_weights(criteria, matrix, ['Benefit'] * n)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=10)
            w, _ = calculate_fucom_weights(criteria,criteria,[1.2]*(n-1))
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=8)
            b2o=np.linspace(1,7,n); o2w=np.linspace(7,1,n)
            w, _ = calculate_bwm_weights(criteria,0,n-1,b2o,o2w)
            self.assertTrue(np.isfinite(w).all()); self.assertAlmostEqual(w.sum(), 1, places=8)

    def test_structural_methods_on_random_networks(self):
        rng = np.random.default_rng(1234)
        for n in range(2, 12):
            nodes = [f'N{i}' for i in range(n)]
            direct = rng.integers(0, 5, size=(n,n)).astype(float); np.fill_diagonal(direct, 0)
            steps = _run_dematel(direct, nodes)
            self.assertEqual(steps[-1].table.shape[0], n)
            self.assertTrue(np.isfinite(steps[-1].table.select_dtypes(include=[np.number])).all().all())
            ssim = np.full((n,n), '', dtype=object)
            for i in range(n):
                for j in range(i+1,n): ssim[i,j] = 'V' if rng.random() < .6 else 'O'
            ism_steps = _run_ism(ssim, nodes)
            self.assertEqual(len(ism_steps[-1].table), n)
            self.assertTrue(ism_steps[-1].table['Level'].between(1,n).all())
            anp = rng.uniform(.1, 1, size=(n,n)); anp /= anp.sum(axis=0, keepdims=True)
            anp_weights, anp_steps = _run_anp(anp, nodes)
            self.assertAlmostEqual(float(anp_weights.sum()), 1, places=10)
            self.assertAlmostEqual(anp_steps[-1].table['Limiting priority'].sum(), 1, places=10)

    def test_method_edge_cases_fail_with_actionable_errors(self):
        d = self.demo
        with self.assertRaisesRegex(ValueError, 'diagonal'):
            bad = d['dematel'].copy(); bad[0,0] = 1; _run_dematel(bad, d['criteria'])
        with self.assertRaisesRegex(ValueError, 'V, A, X, O'):
            bad = d['ism'].copy(); bad[0,1] = '?'; _run_ism(bad, d['criteria'])
        with self.assertRaisesRegex(ValueError, 'column must sum to 1'):
            _run_anp(np.eye(4)*.5, d['criteria'])
        with self.assertRaisesRegex(ValueError, 'positive'):
            run_ranking('ARAS', [[0, 1], [1, 2]], ['A','B'], ['C1','C2'], ['Benefit','Cost'], [.5,.5])

    def test_audit_source_is_exportable_python_for_every_method(self):
        methods = ['AHP','ANP','SWARA','BWM','FUCOM','Entropy weights','CRITIC','MEREC','Standard deviation','PSI weights','DEMATEL','ISM',*RANKING_METHODS]
        for method in methods:
            with self.subTest(method=method):
                source = get_audit_code(method)
                compile(source, f'{method}_audit.py', 'exec')
                self.assertIn('def ', source)
                self.assertIn('import numpy as np', source)

    def test_audit_functions_execute_on_demo_data(self):
        d = self.demo; methods = ['AHP','ANP','SWARA','BWM','FUCOM','Entropy weights','CRITIC','MEREC','Standard deviation','PSI weights','DEMATEL','ISM',*RANKING_METHODS]
        for method in methods:
            with self.subTest(method=method):
                namespace = {}; exec(compile(get_audit_code(method), f'{method}_audit.py', 'exec'), namespace)
                if method == 'AHP': result = namespace['calculate_ahp'](d['criteria'], d['ahp'])
                elif method == 'ANP': result = namespace['_run_anp'](d['anp'], d['criteria'])
                elif method == 'SWARA': result = namespace['calculate_swara'](d['criteria'], d['swara'])
                elif method == 'BWM':
                    c=d['bwm']; result=namespace['calculate_bwm_weights'](d['criteria'],c['best_idx'],c['worst_idx'],c['best_to_others'],c['others_to_worst'])
                elif method == 'Entropy weights': result = namespace['calculate_entropy_weights'](d['criteria'], d['matrix'], d['directions'])
                elif method == 'CRITIC': result = namespace['calculate_critic_weights'](d['criteria'], d['matrix'], d['directions'])
                elif method == 'MEREC': result = namespace['calculate_merec_weights'](d['criteria'], d['matrix'], d['directions'])
                elif method == 'Standard deviation': result = namespace['calculate_std_weights'](d['criteria'], d['matrix'], d['directions'])
                elif method == 'PSI weights': result = namespace['calculate_psi_weights'](d['criteria'], d['matrix'], d['directions'])
                elif method == 'FUCOM': result = namespace['calculate_fucom_weights'](d['criteria'],d['criteria'],[1.5,1.2,1.1])
                elif method == 'DEMATEL': result = namespace['_run_dematel'](d['dematel'], d['criteria'])
                elif method == 'ISM': result = namespace['_run_ism'](d['ism'], d['criteria'])
                elif method == 'MOORA': result = namespace['_run_moora'](d['matrix'], d['alternatives'], d['criteria'], d['directions'])
                elif method == 'MULTIMOORA': result = namespace['_run_multimoora'](d['matrix'], d['alternatives'], d['criteria'], d['directions'])
                elif method == 'WASPAS': result = namespace['_run_waspas'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'VIKOR': result = namespace['_run_vikor'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'ELECTRE I': result = namespace['_run_electre1'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'PROMETHEE II': result = namespace['_run_promethee2'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'CoCoSo': result = namespace['_run_cocoso'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'EDAS': result = namespace['_run_edas'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'MARCOS': result = namespace['_run_marcos'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'CODAS': result = namespace['_run_codas'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'MAIRCA': result = namespace['_run_mairca'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'MABAC': result = namespace['_run_mabac'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'GRA': result = namespace['_run_gra'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                elif method == 'PIV': result = namespace['_run_piv'](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                else:
                    key = {'SAW':'_run_saw','TOPSIS':'_run_topsis','COPRAS-G':'_run_copras','ARAS':'_run_aras'}[method]
                    result = namespace[key](d['matrix'], d['alternatives'], d['criteria'], d['directions'], np.array(d['weights']))
                self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
