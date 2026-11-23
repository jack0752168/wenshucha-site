import copy
import json
import tempfile
import unittest
from pathlib import Path
from crm_store import upsert_trial, save_merged


class CRMTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name)/'pipeline.json'
        self.original = {'meta': {}, 'companies': [{'id': 'paid', 'name': 'Existing', 'stage': 5, 'contacts': [], 'notes': 'paid untouched'}]}
        self.file.write_text(json.dumps(self.original))
        self.lead = {'id': 'trial-one', 'source': 'mcp-selfserve', 'email_verified': True, 'phone_verified': False,
                     'profile': {'name': '张三', 'company': '某某有限公司', 'phone': '13800000001', 'email': 'one@example.com'},
                     'plan': 'free', 'expires': '2026-12-23', 'issued_day': '2026-11-23', 'key_mask': 'wsc_free_…abcd'}

    def test_idempotence_and_no_outreach(self):
        one = upsert_trial(self.file, self.lead)
        two = upsert_trial(self.file, self.lead)
        self.assertEqual(one, two)
        data = json.loads(self.file.read_text())
        self.assertEqual(len(data['companies']), 2)
        self.assertEqual(data['companies'][0], self.original['companies'][0])
        lead = data['companies'][1]
        self.assertEqual(lead['stage'], 4)
        self.assertEqual(lead['contacts'][0]['status'], 'manual-only')
        self.assertEqual(len(lead['mcp_trials']), 1)

    def test_existing_customer_fields_preserved(self):
        self.lead['profile']['company'] = 'Existing'
        upsert_trial(self.file, self.lead)
        data = json.loads(self.file.read_text())
        self.assertEqual(len(data['companies']), 1)
        self.assertEqual(data['companies'][0]['stage'], 5)
        self.assertEqual(data['companies'][0]['notes'], 'paid untouched')

    def test_unverified_rejected_and_concurrent_save_merges_new_lead(self):
        unverified = copy.deepcopy(self.lead)
        unverified['email_verified'] = False
        with self.assertRaises(ValueError):
            upsert_trial(self.file, unverified)
        upsert_trial(self.file, self.lead)
        desired = copy.deepcopy(self.original)
        desired['companies'][0]['notes'] = 'new paid note'
        save_merged(self.file, self.original, desired)
        data = json.loads(self.file.read_text())
        self.assertEqual(len(data['companies']), 2)
        self.assertEqual(data['companies'][0]['notes'], 'new paid note')


if __name__ == '__main__':
    unittest.main()
