import unittest
from Section_1_Global_Core.memory_storage.Audit.audit_runner import summarize


class AuditReportingTests(unittest.TestCase):
    def manifest(self):
        return {'A1':{'failed':0},'A2':[],'A3':{'ran':False},'A4':[], 'A5':{'stale_count':0,'missing':0}}

    def test_stale_history_fails_freshness_without_claiming_wrong_prices(self):
        manifest=self.manifest();manifest['A5']['stale_count']=4
        result=summarize(manifest)
        self.assertFalse(result['pass']);self.assertTrue(result['schema_pass'])
        self.assertFalse(result['freshness_pass']);self.assertEqual(result['source_verification'],'not-run')

    def test_source_mismatch_and_consistency_failure_cannot_report_pass(self):
        manifest=self.manifest();manifest['A3']={'ran':True,'issues':[{'mismatch_count':1}]}
        self.assertFalse(summarize(manifest)['pass'])
        manifest=self.manifest();manifest['A4']=[{'pairs':[{'mismatch_count':1}]}]
        self.assertFalse(summarize(manifest)['pass'])

    def test_missing_data_is_not_fresh(self):
        manifest=self.manifest();manifest['A5']['missing']=1
        self.assertFalse(summarize(manifest)['freshness_pass'])

    def test_disabled_or_empty_source_check_does_not_claim_verification(self):
        manifest=self.manifest();manifest['A3']={'ran':True,'enabled':False,'issues':[]}
        self.assertEqual(summarize(manifest)['source_verification'],'disabled')
        manifest['A3']={'ran':True,'enabled':True,'samples_checked':0,'issues':[]}
        self.assertEqual(summarize(manifest)['source_verification'],'not-verified')
