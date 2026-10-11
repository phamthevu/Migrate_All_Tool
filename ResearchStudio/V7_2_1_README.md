# Research Studio V7.2.1

Canonical project identity release.

- `storage_key` is the canonical technical name across DB tables and generated snapshot filenames.
- Snapshot files: `<storage_key>_<UTC stamp>.json`, `_RAW_CODES.xlsx`, `_NUMERICAL_VALUES.xlsx`.
- S3 / Google Drive / Cloud Sync Folder project snapshots use `<storage_key>/snapshots/<snapshot_id>/...`.
- Email current snapshot uses the same canonical filenames as S3/Drive.
- Human `project_name` remains display metadata only.
- BigQuery is intentionally a configured shared destination table; every row carries `project_id`. It does not create per-project physical tables.
- Power BI/Webhook are endpoint-based connectors and do not define filenames.
- ADLS/FTP/SFTP remain generic transfer/test connectors in this release; when files are passed, their local canonical basename must be preserved. They are not part of Data Sync Manager's project snapshot destinations.
- Release ZIP has a single top-level `project/` directory for clean Git extraction/import.
