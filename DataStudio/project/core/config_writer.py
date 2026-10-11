import os,tempfile
from pathlib import Path
import pandas as pd

def save_config(path,config,scale,weights,dematel=None):
    dest=Path(path);fd,tmp=tempfile.mkstemp(suffix='.xlsx',dir=dest.parent);os.close(fd)
    try:
        with pd.ExcelWriter(tmp,engine='openpyxl') as writer:
            pd.DataFrame({'RowName':pd.Series(config.rows),'ColumnName':pd.Series(config.cols)}).to_excel(writer,sheet_name='Config',index=False)
            scale.to_excel(writer,sheet_name='Fuzzy',index=False);weights.to_excel(writer,sheet_name='Weights',index=False)
            if config.adv_df is not None:config.adv_df.to_excel(writer,sheet_name='Advance',index=False)
            if dematel is not None:dematel.to_excel(writer,sheet_name='DEMATEL',index=False)
            elif config.dematel_df is not None:config.dematel_df.to_excel(writer,sheet_name='DEMATEL',index=False)
            if config.order_df is not None:config.order_df.to_excel(writer,sheet_name='Order',index=False)
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
