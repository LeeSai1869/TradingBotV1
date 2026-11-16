"""Lossless JSON storage with small, immutable shared zlib dictionaries.

The connection decodes marked BLOBs before returning rows. Canonical JSON used
for identities/hashes stays unchanged; unrelated BLOBs and plain legacy text pass
through. Use this connection for Section 5 reads, including read-only research.
"""
from collections import OrderedDict
import hashlib
import sqlite3
import weakref
import zlib

PLAIN=b'\x00S5JSON1'
SHARED=b'\x00S5JSON2'


class Connection(sqlite3.Connection):
    def close(self):
        try:super().close()
        finally:self._section5_dictionaries.clear()


def _dictionary(conn,key):
    cache=conn._section5_dictionaries
    if key in cache:
        cache.move_to_end(key);return cache[key]
    cursor=conn.cursor();cursor.row_factory=None
    try:row=cursor.execute('SELECT dictionary FROM _section5_json_dictionaries WHERE id=?',(key,)).fetchone()
    finally:cursor.close()
    if row is None:raise sqlite3.DataError('Missing Section 5 compression dictionary')
    value=row[0]
    if hashlib.sha256(value).digest()!=key:raise sqlite3.DataError('Corrupt Section 5 compression dictionary')
    cache[key]=value
    if len(cache)>64:cache.popitem(last=False)
    return value


def unpack(conn,value):
    if not isinstance(value,bytes):return value
    try:
        if value.startswith(PLAIN):return zlib.decompress(value[len(PLAIN):]).decode('utf-8')
        if value.startswith(SHARED):
            start=len(SHARED);end=start+32
            obj=zlib.decompressobj(zdict=_dictionary(conn,value[start:end]))
            raw=obj.decompress(value[end:])+obj.flush()
            if not obj.eof or obj.unused_data:raise sqlite3.DataError('Invalid Section 5 compressed JSON')
            return raw.decode('utf-8')
    except (zlib.error,UnicodeError) as error:
        raise sqlite3.DataError('Corrupt Section 5 compressed JSON') from error
    return value


def connect(path,*,readonly=False,timeout=5,row_factory=None,compact=False):
    conn=sqlite3.connect(path.resolve().as_uri()+('?mode=ro' if readonly else '?mode=rwc'),
        uri=True,timeout=timeout,factory=Connection)
    conn._section5_dictionaries=OrderedDict()
    conn._section5_compact=compact
    reference=weakref.ref(conn)
    def decode(cursor,row):
        values=tuple(unpack(reference(),value) for value in row)
        return row_factory(cursor,values) if row_factory else values
    conn.row_factory=decode
    if readonly:conn.execute('PRAGMA query_only=ON')
    return conn


def create_schema(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS _section5_json_dictionaries (
            id BLOB PRIMARY KEY,dictionary BLOB NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS _section5_run_dictionaries (
            run_id TEXT PRIMARY KEY,dictionary_id BLOB NOT NULL
            REFERENCES _section5_json_dictionaries(id)) WITHOUT ROWID;
    ''')


def seed_dictionary(conn,run_id,value):
    old=conn.execute('SELECT dictionary_id FROM _section5_run_dictionaries WHERE run_id=?',(run_id,)).fetchone()
    if old:return old[0]
    value=value[-32768:];key=hashlib.sha256(value).digest()
    conn.execute('INSERT OR IGNORE INTO _section5_json_dictionaries VALUES (?,?)',(key,value))
    conn.execute('INSERT INTO _section5_run_dictionaries VALUES (?,?)',(run_id,key))
    return key


def pack(conn,value,*,dictionary_id=None):
    if value is None:return None
    if not isinstance(value,str):raise TypeError('Section 5 JSON must be text')
    if not conn._section5_compact:return value
    raw=value.encode('utf-8')
    if dictionary_id is None:
        packed=PLAIN+zlib.compress(raw,6)
    else:
        obj=zlib.compressobj(6,zlib.DEFLATED,zlib.MAX_WBITS,zdict=_dictionary(conn,dictionary_id))
        packed=SHARED+dictionary_id+obj.compress(raw)+obj.flush()
    return packed if len(packed)<len(raw) else value
