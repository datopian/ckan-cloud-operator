import unittest

from click.testing import CliRunner


class BaseCliTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
