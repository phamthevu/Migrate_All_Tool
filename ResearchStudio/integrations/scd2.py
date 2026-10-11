from datetime import datetime,timezone
def apply_scd2(history,business_key,new_record,tracked_fields=None,at=None):
    '''Pure helper for analytics/warehouse dimensions; core operational responses remain current-state + audit/CDC.'''
    at=at or datetime.now(timezone.utc).isoformat(timespec='seconds'); tracked_fields=tracked_fields or [k for k in new_record if k!=business_key]
    cur=next((r for r in history if r.get(business_key)==new_record.get(business_key) and r.get('is_current')),None)
    if cur and all(cur.get(k)==new_record.get(k) for k in tracked_fields): return history,False
    if cur: cur['valid_to']=at;cur['is_current']=False
    row=dict(new_record);row['valid_from']=at;row['valid_to']=None;row['is_current']=True;history.append(row);return history,True
