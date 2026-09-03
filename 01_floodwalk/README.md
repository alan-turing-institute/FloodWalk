# FloodWalk

iOS Spotlight forensic artefact parser. Converts CoreSpotlight
`store.db` files into a single SQLite database for analysis.

## Files

* `spotlight_parser.py` — store.db parser. Modified copy of
  `ydkhatri/spotlight_parser` (commit `dd96e63`, 2025-12-07, GPL v3);
  initialises `v = None` in `FileMetaDataListing.ParseItem` so the 
  parser does not raise `UnboundLocalError` on the "error getting category"
  path that iOS Spotlight stores trigger.
* `spotlight_to_sqlite.py` — wrapper that walks the four iOS Spotlight
  stores and emits a SQLite database with `source`, `items`, and `props`
  tables.
* `floodwalk_example.sqlite` — redacted exemplar derived from running
  this parser over the iPhone 17e Ex3 Spotlight stores, demonstrating
  5 items.

## Usage

Tested under Python 3.13.

```
pip install -r requirements.txt
python3 spotlight_to_sqlite.py \
  /path/to/Spotlight/CoreSpotlight/<protection-class>/index.spotlightV2 \
  out.sqlite
```

Run once per protection class, pointing each invocation at the same
`out.sqlite`; the wrapper appends to the existing tables. E.g. Run on
`NSFileProtectionComplete`,
`NSFileProtectionCompleteUnlessOpen`,
`NSFileProtectionCompleteWhenUserInactive`, and
`NSFileProtectionCompleteUntilFirstUserAuthentication`.
