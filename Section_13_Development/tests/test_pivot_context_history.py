"""Real SQLite snapshots, current publication index and no-write guarantees."""
import hashlib
import json
import unittest
from unittest.mock import patch
import test_pivot_research as fixtures
from Section_1_Global_Core import pivot_context_audit as audit,pivot_research,regime_research,regime_inputs,aggregation_processor,aggregation_store,intelligence_audit
from Section_1_Global_Core.memory_storage.Storage import features_store,klines_store,engine_store

class ContextHistory(unittest.TestCase):
    def setUp(self):
        fixtures.PivotCohort.setUp(self)
    def test_current_indexed_results_only_and_ro_audit_preserves_databases(self):
        report=pivot_research.scan('BTCUSDT','1m',now_ms=10**9)
        batch=regime_research.catch_up('BTCUSDT','1m',limit=100,now_ms=10**9)
        aggregation_processor.observe('BTCUSDT','1m','REGIME',batch,now_ms=10**9)
        paths=[features_store.DB_PATH,klines_store.DB_PATH,engine_store.DB_PATH]
        digest=lambda:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        before=digest()
        source=regime_inputs.open_sources()
        try:
            with intelligence_audit.reader() as engines:
                reader=audit.LocalReader(source,engines,report)
                self.assertEqual(reader.run_status['1m:REGIME'],'READY')
                self.assertEqual(reader.run_status['4h:REGIME'],'NOT_INDEXED')
                result=audit.audit(report,reader)
        finally:source.close()
        self.assertEqual(len(result['cases']),3)
        self.assertEqual(result['cases'][0]['context_at_recognition']['1m']['REGIME']['run_id'],batch['run_id'])
        self.assertIsNone(result['cases'][0]['context_at_recognition']['4h']['REGIME']['classification'])
        json.dumps(result,allow_nan=False)
        self.assertEqual(before,digest())
