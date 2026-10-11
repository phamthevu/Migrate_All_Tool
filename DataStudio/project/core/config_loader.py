from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class ConfigData:
    rows: list
    cols: list
    fuzzy_df: pd.DataFrame
    adv_df: object = None
    weights_df: object = None
    order_df: object = None
    dematel_df: object = None
    @property
    def m(self): return len(self.rows)
    @property
    def n(self): return len(self.cols)

def validate_scale(df):
    df = df.rename(columns={'Linguistic': 'Lingustic'}).copy()
    missing = {'Lingustic','Fuzzy','Level'} - set(df.columns)
    if missing: raise ValueError(f'Fuzzy is missing columns: {sorted(missing)}')
    if df.empty or df[['Lingustic','Fuzzy','Level']].isna().any().any():
        raise ValueError('The Fuzzy scale is empty or has missing values.')
    for c in ('Lingustic','Fuzzy'):
        df[c] = df[c].astype(str).str.strip()
        if (df[c] == '').any() or df[c].duplicated().any():
            raise ValueError(f'{c} must be nonempty and unique for two-way conversion.')
    df['Level'] = pd.to_numeric(df['Level'], errors='raise')
    if not np.isfinite(df['Level']).all(): raise ValueError('Level must be finite.')
    if 'Probability' not in df: df['Probability'] = 1.0
    df['Probability'] = pd.to_numeric(df['Probability'], errors='raise')
    if not np.isfinite(df['Probability']).all() or (df['Probability'] < 0).any() or df['Probability'].sum() <= 0:
        raise ValueError('Probability must be nonnegative, finite and sum to more than 0.')
    return df

def load_config_excel(path):
    sheets = pd.read_excel(path, sheet_name=None)
    if not {'Config','Fuzzy'} <= set(sheets): raise ValueError('Config and Fuzzy sheets are required.')
    cfg = sheets['Config']
    if not {'RowName','ColumnName'} <= set(cfg): raise ValueError('Config requires RowName and ColumnName.')
    names = []
    for c in ('RowName','ColumnName'):
        values = cfg[c].dropna().astype(str).str.strip().tolist()
        if not values or any(not x for x in values) or len(set(values)) != len(values):
            raise ValueError(f'{c} must be nonempty and unique.')
        names.append(values)
    result = ConfigData(*names, validate_scale(sheets['Fuzzy']), sheets.get('Advance'), sheets.get('Weights'),sheets.get('Order'),sheets.get('DEMATEL'))
    if result.weights_df is not None:
        w = result.weights_df
        if not {'Criterion','Weight'} <= set(w): raise ValueError('Weights requires Criterion and Weight.')
        if w['Criterion'].duplicated().any() or set(w['Criterion']) != set(result.rows):
            raise ValueError('Weights must contain each RowName exactly once.')
        a = pd.to_numeric(w['Weight'], errors='raise')
        if not np.isfinite(a).all() or (a <= 0).any(): raise ValueError('Weight must be positive and finite.')
    if result.order_df is not None:
        order=result.order_df.copy()
        if not {'Criterion','Rank'} <= set(order):raise ValueError('Order requires Criterion and Rank (1 = highest).')
        order['Criterion']=order['Criterion'].astype(str).str.strip()
        if order['Criterion'].duplicated().any() or set(order['Criterion'])!=set(result.rows):raise ValueError('Order must contain each RowName exactly once.')
        ranks=pd.to_numeric(order['Rank'],errors='raise')
        if set(ranks)!=set(range(1,result.m+1)):raise ValueError('Order ranks must be a permutation of 1..number of rows.')
        result.order_df=order.assign(Rank=ranks.astype(int))
    if result.dematel_df is not None:
        d=result.dematel_df
        if not {'Criterion','Prominence','Role','Strength'}<=set(d) or d.Criterion.duplicated().any() or set(d.Criterion)!=set(result.rows):
            raise ValueError('DEMATEL requires each Criterion once, with Prominence, Role, Strength.')
        from .dematel import profile_arrays
        profile_arrays(result.rows,d.set_index('Criterion').to_dict('index'))
    return result
