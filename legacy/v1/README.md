# TickEye v1 migration inputs

This directory contains the only v1 files still needed by V2:

- `funds_config.json`: the former mixed fund/index watch configuration.
- `indices_config.json`: aliases used to distinguish legacy index symbols from funds.

They are migration inputs, not V2 runtime configuration. Run
`tickeye-migrate-v1` to preview them. Fund and ETF entries can be migrated into
a user watchlist; index entries remain deferred until V2 defines an explicit
benchmark model.

The v1 Python entry points, Feishu integration, duplicated dependency file, and
outdated documentation were removed after their relevant market-data behavior
was captured by `tests/contract/test_akshare_provider.py`.

After the migration is confirmed and backed up, this entire directory can be
removed in the final v1 retirement step.
