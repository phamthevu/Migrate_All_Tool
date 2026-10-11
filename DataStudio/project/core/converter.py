import pandas as pd
from .config_loader import validate_scale

def build_converter_maps(fuzzy_df):
    df=validate_scale(fuzzy_df)
    return dict(zip(df.Lingustic,df.Fuzzy)),dict(zip(df.Fuzzy,df.Lingustic))

def convert_df(df, mode, fuzzy_df):
    if mode not in ('LING_TO_FUZZY','FUZZY_TO_LING'): raise ValueError('Invalid conversion mode.')
    forward,reverse=build_converter_maps(fuzzy_df)
    mapping=forward if mode=='LING_TO_FUZZY' else reverse
    def cell(v):
        if pd.isna(v): return v
        return mapping.get(str(v).strip(),v)
    return df.astype(object).map(cell) if hasattr(df,'map') else df.astype(object).applymap(cell)
