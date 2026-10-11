class ADLSRepository:
    def __init__(self,cfg): self.cfg=cfg
    def _client(self):
        try: from azure.storage.blob import BlobServiceClient
        except ImportError: raise RuntimeError('Install azure-storage-blob to use Azure Blob / ADLS Gen2.')
        c=self.cfg; return BlobServiceClient(account_url=c.get('account_url'),credential=c.get('credential'))
    def test(self):
        svc=self._client(); next(iter(svc.list_containers(results_per_page=1)),None); return {'ok':True}
    def upload_bytes(self,name,data):
        c=self.cfg; bc=self._client().get_blob_client(container=c.get('container'),blob=(c.get('prefix','research-studio').strip('/')+'/'+name).lstrip('/')); bc.upload_blob(data,overwrite=True); return {'blob':bc.blob_name}
