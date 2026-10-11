import tempfile,os,random
from integrations.cdc_engine import RowCDC
from integrations.scd2 import apply_scd2

def main():
    f=tempfile.NamedTemporaryFile(delete=False);f.close(); c=RowCDC(f.name); pid='P1'
    rows=[{'id':str(i),'v':i} for i in range(10000)]
    ev=c.capture(pid,'responses',rows,'id'); assert len(ev)==10000 and all(x[1]=='I' for x in ev)
    assert c.capture(pid,'responses',rows,'id')==[]
    for i in range(0,10000,10): rows[i]['v']+=1
    ev=c.capture(pid,'responses',rows,'id'); assert len(ev)==1000 and all(x[1]=='U' for x in ev)
    rows=rows[:-500]; ev=c.capture(pid,'responses',rows,'id'); assert len(ev)==500 and all(x[1]=='D' for x in ev)
    hist=[]
    for i in range(10000): hist,changed=apply_scd2(hist,'id',{'id':'E1','org':'A' if i<5000 else 'B'},['org'],str(i));
    assert len(hist)==2 and hist[0]['is_current']==False and hist[1]['is_current']==True
    assert len(c.events(pid,0,20000))==11500
    os.unlink(f.name); print('V5.2 CDC/SCD STRESS PASS: 10k insert, 1k update, 500 tombstone, 10k SCD2 calls')
if __name__=='__main__':main()
