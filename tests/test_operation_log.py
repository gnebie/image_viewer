import unittest

from image_viewer.operation_log import OperationLog, OperationRecord


class OperationLogTests(unittest.TestCase):
    def test_keeps_most_recent_max_items(self) -> None:
        log = OperationLog(max_items=2)
        log.add(OperationRecord(kind="k1", src="a", dest="b"))
        log.add(OperationRecord(kind="k2", src="a", dest="b"))
        log.add(OperationRecord(kind="k3", src="a", dest="b"))
        items = list(log.items())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].kind, "k3")
        self.assertEqual(items[1].kind, "k2")


if __name__ == "__main__":
    unittest.main()
