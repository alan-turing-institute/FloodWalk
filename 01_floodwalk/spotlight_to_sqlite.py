#!/usr/bin/env python3
"""
Export Spotlight store.db (iOS CoreSpotlight) to SQLite.
Search via props.value_text LIKE '%term%'.

Usage:
  python3 spotlight_to_sqlite.py /path/to/store.db out.sqlite
  python3 spotlight_to_sqlite.py /path/to/index.spotlightV2 out.sqlite
"""

import os
import sys
import time
import sqlite3
import logging

import spotlight_parser as sp

log = logging.getLogger("SPOTLIGHT_SQLITE")

# Tune this if you care about limiting large fields: higher = bigger DB.
MAX_TEXT = 65535  # 64 KiB per property value (cap)

SCHEMA_TABLES_ONLY = """
PRAGMA journal_mode=OFF;
PRAGMA synchronous=OFF;
PRAGMA temp_store=MEMORY;
PRAGMA locking_mode=EXCLUSIVE;
PRAGMA cache_size=-200000;  -- ~200MB cache (adjust down if needed)

CREATE TABLE IF NOT EXISTS source (
  id INTEGER PRIMARY KEY,
  input_path TEXT NOT NULL,
  original_path TEXT,
  is_ios_store INTEGER NOT NULL,
  version INTEGER NOT NULL,
  created_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
  rowid INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL,

  spotlight_id INTEGER,
  store_id INTEGER,
  parent_spotlight_id INTEGER,
  flags INTEGER,

  date_updated_us INTEGER,
  date_updated_utc TEXT
);

CREATE TABLE IF NOT EXISTS props (
  item_rowid INTEGER NOT NULL,
  prop_name TEXT NOT NULL,
  value_text TEXT,
  PRIMARY KEY (item_rowid, prop_name)
);
"""

INDEXES_AFTER_LOAD = """
CREATE INDEX IF NOT EXISTS idx_items_date      ON items(date_updated_us);

CREATE INDEX IF NOT EXISTS idx_props_name      ON props(prop_name);
CREATE INDEX IF NOT EXISTS idx_props_item      ON props(item_rowid);
"""

def _resolve_input(input_path: str) -> str:
    if os.path.isdir(input_path):
        candidate = os.path.join(input_path, "store.db")
        if not os.path.exists(candidate):
            raise FileNotFoundError(f"Folder provided but store.db not found: {candidate}")
        return candidate
    return input_path

def _prepare_store(store_db_path: str) -> "sp.SpotlightStore":
    f = open(store_db_path, "rb")
    store = sp.SpotlightStore(f)

    if store.is_ios_store:
        input_folder = os.path.dirname(os.path.abspath(store_db_path))
        if not os.path.isfile(os.path.join(input_folder, "dbStr-1.map.data")):
            raise FileNotFoundError(
                "iOS store detected but dbStr-* files missing. "
                "Extract the entire index.spotlightV2 folder (store.db + dbStr*)."
            )

        prop_map_data, prop_map_offsets, prop_map_header = sp.GetMapDataOffsetHeader(input_folder, 1)
        cat_map_data, cat_map_offsets, cat_map_header = sp.GetMapDataOffsetHeader(input_folder, 2)
        idx_1_map_data, idx_1_map_offsets, idx_1_map_header = sp.GetMapDataOffsetHeader(input_folder, 4)
        idx_2_map_data, idx_2_map_offsets, idx_2_map_header = sp.GetMapDataOffsetHeader(input_folder, 5)

        store.ParsePropertiesFromFileData(prop_map_data, prop_map_offsets, prop_map_header)
        store.ParseCategoriesFromFileData(cat_map_data, cat_map_offsets, cat_map_header)
        store.ParseIndexesFromFileData(idx_1_map_data, idx_1_map_offsets, idx_1_map_header, store.indexes_1)
        store.ParseIndexesFromFileData(idx_2_map_data, idx_2_map_offsets, idx_2_map_header, store.indexes_2, has_extra_byte=True)

        store.ReadPageIndexesAndOtherDefinitions(True)
    else:
        store.ReadPageIndexesAndOtherDefinitions()

    return store

def _monkeypatch_no_print():
    original_print = sp.FileMetaDataListing.Print
    def Print(self, file):
        if file is None:
            return
        return original_print(self, file)
    sp.FileMetaDataListing.Print = Print

def _to_text(v):
    """Make everything searchable in value_text (bytes become hex preview)."""
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        s = bytes(v).hex().upper()
        return s[:MAX_TEXT]
    if isinstance(v, (list, tuple)):
        s = " ".join(str(x) for x in v)
        return s[:MAX_TEXT]
    s = str(v)
    return s[:MAX_TEXT]

class Sink:
    def __init__(self, sqlite_path: str, batch_size: int = 5000):
        self.conn = sqlite3.connect(sqlite_path)
        self.conn.executescript(SCHEMA_TABLES_ONLY)
        self.batch_size = batch_size
        self.source_id = None

        self._pending = []  # [(item_tuple, [(prop_name, value_text), ...]), ...]
        self._n = 0

    def begin_source(self, input_path: str, original_path: str, is_ios_store: bool, version: int):
        created_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO source(input_path, original_path, is_ios_store, version, created_utc) VALUES(?,?,?,?,?)",
            (input_path, original_path, int(is_ios_store), int(version), created_utc),
        )
        self.source_id = cur.lastrowid
        self.conn.commit()

    def add_item(self, md_item: "sp.FileMetaDataListing"):
        md = md_item.meta_data_dict

        date_us = getattr(md_item, "date_updated", None)
        date_utc = ""
        if hasattr(md_item, "ConvertEpochToUtcDateStr") and date_us is not None:
            date_utc = str(md_item.ConvertEpochToUtcDateStr(date_us))

        item_tuple = (
            self.source_id,
            getattr(md_item, "id", None),
            getattr(md_item, "item_id", None),
            getattr(md_item, "parent_id", None),
            getattr(md_item, "flags", None),
            date_us,
            date_utc,
        )

        props = []
        for k, v in md.items():
            props.append((k, _to_text(v)))

        self._pending.append((item_tuple, props))
        self._n += 1
        if self._n % self.batch_size == 0:
            self.flush()

    def flush(self):
        if not self._pending:
            return
        cur = self.conn.cursor()
        cur.execute("BEGIN;")
        try:
            # rowid range trick for fast mapping
            max_before = cur.execute("SELECT IFNULL(MAX(rowid), 0) FROM items").fetchone()[0]

            items_only = [it for (it, _) in self._pending]
            cur.executemany(
                """
                INSERT INTO items(
                  source_id, spotlight_id, store_id, parent_spotlight_id, flags,
                  date_updated_us, date_updated_utc
                ) VALUES(?,?,?,?,?,?,?)
                """,
                items_only,
            )

            base_rowid = max_before + 1

            props_flat = []
            for idx, (_, props) in enumerate(self._pending):
                item_rowid = base_rowid + idx
                for (prop_name, value_text) in props:
                    props_flat.append((item_rowid, prop_name, value_text))

            cur.executemany(
                "INSERT OR REPLACE INTO props(item_rowid, prop_name, value_text) VALUES(?,?,?)",
                props_flat,
            )

            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self._pending.clear()

    def finalize(self):
        self.flush()
        # Build indexes AFTER load (much faster overall)
        self.conn.executescript(INDEXES_AFTER_LOAD)
        self.conn.commit()
        self.conn.close()

def export_to_sqlite(input_path: str, sqlite_path: str):
    store_db_path = _resolve_input(input_path)
    t0 = time.time()

    store = _prepare_store(store_db_path)
    sink = Sink(sqlite_path, batch_size=5000)
    sink.begin_source(
        input_path=os.path.abspath(store_db_path),
        original_path=getattr(store, "original_path", None),
        is_ios_store=store.is_ios_store,
        version=store.version,
    )

    def process_items(items_in_block, _is_ios):
        for md_item in items_in_block:
            sink.add_item(md_item)

    store.ParseMetadataBlocks(
        output_file=None,
        items={},
        items_to_compare=None,
        process_items_func=process_items,
    )

    sink.finalize()
    store.file.close()

    elapsed = time.time() - t0
    log.info("SQLite written: %s", sqlite_path)
    log.info("Elapsed: %s", time.strftime("%H:%M:%S", time.gmtime(elapsed)))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    if len(sys.argv) != 3:
        print("Usage: python3 spotlight_to_sqlite_fast.py <store.db OR index.spotlightV2 folder> <out.sqlite>")
        sys.exit(2)

    _monkeypatch_no_print()
    export_to_sqlite(sys.argv[1], sys.argv[2])
