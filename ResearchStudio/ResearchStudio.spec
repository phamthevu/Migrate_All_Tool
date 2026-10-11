from PyInstaller.utils.hooks import collect_submodules
hidden=[]
for pkg in ['keyring.backends','psycopg2','pymysql','boto3','botocore','paramiko','pymongo','azure.storage.blob','google.auth','googleapiclient','google.cloud.bigquery']:
    try:hidden += collect_submodules(pkg)
    except Exception:pass

a=Analysis(['main.py'],pathex=[],binaries=[],datas=[],hiddenimports=hidden,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='ResearchStudio',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,console=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=True,upx_exclude=[],name='ResearchStudio')
