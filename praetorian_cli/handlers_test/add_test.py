import unittest
from click.testing import CliRunner
from unittest import mock
from praetorian_cli.handlers.add import add
from praetorian_cli.handlers.chariot import chariot


class TestAddCommands(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_add_asset(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['add', 'asset', '--name', 'test_asset', '--dns', 'test_dns'])
        self.assertEqual(result.exit_code, 0)
        controller.add.assert_called_once_with('asset', {'name': 'test_asset', 'dns': 'test_dns', 'status': 'A'})

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_upload_file(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['add', 'file', 'test_file'])
        self.assertEqual(result.exit_code, 0)
        controller.upload.assert_called_once_with('test_file', None)

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_upload_definition(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['add', 'definition', 'test_path'])
        self.assertEqual(result.exit_code, 0)
        controller.upload.assert_called_once_with('test_path', 'definitions/test_path')

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_add_webhook(self, MockController):
        controller = MockController.return_value
        controller.add_webhook.return_value = "Webhook added"
        result = self.runner.invoke(chariot, ['add', 'webhook'])
        self.assertEqual(result.exit_code, 0)
        controller.add_webhook.assert_called_once()
        self.assertIn("Webhook added", result.output)

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_add_risk(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['add', 'risk', 'test_risk', '--asset', 'test_asset', '--status', 'TI'])
        self.assertEqual(result.exit_code, 0)
        controller.add.assert_called_once_with('risk', {'key': 'test_asset', 'name': 'test_risk', 'status': 'TI',
                                                        'comment': ''})

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_add_job(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['add', 'job', 'test_capability', '--asset', 'test_asset'])
        self.assertEqual(result.exit_code, 0)
        controller.add.assert_called_once_with('job', {'key': 'test_asset', 'name': 'test_capability'})

    @mock.patch('praetorian_cli.handlers.chariot.Chariot', new_callable=mock.Mock)
    def test_add_attribute(self, MockController):
        controller = MockController.return_value
        result = self.runner.invoke(chariot, ['add', 'attribute', '--key', 'test_key', '--name', 'test_name', '--value',
                                              'test_value'])
        self.assertEqual(result.exit_code, 0)
        controller.add.assert_called_once_with('attribute',
                                               {'key': 'test_key', 'name': 'test_name', 'value': 'test_value'})


if __name__ == '__main__':
    unittest.main()
