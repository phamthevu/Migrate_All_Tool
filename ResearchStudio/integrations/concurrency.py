class SyncConflictError(RuntimeError):
    def __init__(self, local_revision, remote_revision, storage_key):
        self.local_revision=local_revision; self.remote_revision=remote_revision; self.storage_key=storage_key
        super().__init__(f"REMOTE PROJECT HAS CHANGED: storage_key={storage_key}; local revision={local_revision}; database revision={remote_revision}. Refresh/reconcile or explicitly Force Sync.")

def should_block_revision(mode, force, local_revision, remote_revision, remote_exists=True):
    """V7.1: only destructive OVERWRITE requires an exact optimistic-concurrency match.
    APPEND is an immutable snapshot operation and may proceed concurrently.
    """
    if force or str(mode).lower() != 'overwrite' or not remote_exists:
        return False
    if local_revision is None:
        return True
    try:return int(local_revision) != int(remote_revision)
    except Exception:return True
