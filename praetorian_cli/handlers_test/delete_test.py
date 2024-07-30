import unittest
from unittest import mock

from click.testing import CliRunner

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.delete import delete, purge  # noqa


class TestDeleteCommands(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_delete_asset(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['delete', 'asset', 'test_key'])
        self.assertEqual(result.exit_code, 0)
        controller.update.assert_called_once_with('asset', {'key': 'test_key', 'status': 'D'})

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_delete_attribute(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['delete', 'attribute', 'test_key'])
        controller.delete.assert_called_once_with('attribute', 'test_key')
        self.assertEqual(result.exit_code, 0)

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_delete_file(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['delete', 'file', 'test_key'])
        self.assertEqual(result.exit_code, 0)
        controller.delete.assert_called_once_with('file', 'test_key')

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_purge(self, MockController):
        controller = MockController.return_value
        with mock.patch('click.confirm', return_value=True):
            result = self.runner.invoke(chariot, ['purge'])
            self.assertEqual(result.exit_code, 0)
            controller.purge.assert_called_once()
            self.assertIn("Account deleted successfully", result.output)


if __name__ == '__main__':
    unittest.main()
