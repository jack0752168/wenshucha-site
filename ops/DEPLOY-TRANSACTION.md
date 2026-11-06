# Committed site publication

Run `./deploy-to-server.sh` from a clean committed checkout. Every input is
resolved from that script's `SITE_ROOT`; an unrelated `~/wenshucha-site` is not
read. The wrapper checks the live research catalog, archives the checked Git
revision, and builds a SHA-256 manifest of its publishable files.

The cloud checkout is updated with an incremental Git bundle over the existing
SSH connection when needed. Both the wrapper and installer reject older or
divergent source by default. There is no implicit rollback authorization.
Tracked cloud changes cause refusal; unrelated untracked notes are preserved.

After staging, one remote `flock /tmp/sync-wsc.lock` encloses the complete
`publish-site.sh` transaction: checkout update, full guard/template identity
comparison, actual cloud-checkout catalog check, publication, TLS/canonical and
private-file checks, committed public-file hashes, and finally an atomic success
stamp. The existing five-minute cron uses the identical flock path. Staging
outside the lock cannot change webroot or the success stamp.

The cron no longer silently succeeds when fetching Git fails. Missing guard
files, unavailable catalog, dirty tracked source or unprovable ancestry reject
publication without changing webroot/stamp. Final validation failure does not
write a success stamp. A prior known-good site remains the recovery reference.

Bounded checks, all on isolated fixtures:

```
python3 ops/test_deploy_paths.py
python3 ops/test_publication_transaction.py
```

These cover Git/catalog/guard failures, stale and divergent bundles, other
tracked edits, real incremental bundle installation, checked checkout A versus
unrelated HOME B, lock contention, and stamping only after final validation.
They do not publish bad content to the serving site or restart customer services.
