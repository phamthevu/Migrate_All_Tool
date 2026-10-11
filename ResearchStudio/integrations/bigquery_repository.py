from .project_payload import snapshot
class BigQueryRepository:
    def __init__(self,cfg): self.cfg=cfg
    def _client(self):
        try: from google.cloud import bigquery
        except ImportError: raise RuntimeError('Install google-cloud-bigquery to use BigQuery.')
        return bigquery.Client(project=self.cfg.get('project_id') or None)
    def test(self): self._client().query('SELECT 1 AS ok').result(); return {'ok':True}
    def sync(self,db):
        s=snapshot(db); client=self._client(); table=self.cfg.get('responses_table')
        if not table: raise RuntimeError('responses_table is required, e.g. project.dataset.rs_responses')
        import json
        rows=[{'project_id':s['meta']['project_id'],'response_id':str(r.get('id') or ''),'respondent_id':r.get('respondent_id'),'response_json':json.dumps(r,ensure_ascii=False,default=str)} for r in s['responses']]
        errors=client.insert_rows_json(table,rows)
        if errors: raise RuntimeError(str(errors)[:3000])
        return {'responses':len(rows)}
