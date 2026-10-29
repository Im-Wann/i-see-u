import unittest
from tests.mock_data import MOCK_FRAME, MOCK_INCIDENT

class TestPipelineContract(unittest.TestCase):
    def test_mock_data_structure(self):
        self.assertEqual(MOCK_FRAME.shape, (720, 1280, 3))
        self.assertIn("timestamp", MOCK_INCIDENT)
        self.assertIn("event_type", MOCK_INCIDENT)
        self.assertEqual(MOCK_INCIDENT["event_type"], "THEFT_REMOVAL")

if __name__ == "__main__":
    unittest.main()
