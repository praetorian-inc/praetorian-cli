"""Evidence and reporting commands: evidence/report. Mixed into GuardConsole."""

import json


class ReportingCommands:
    """Evidence and reporting console commands. Mixed into GuardConsole."""

    def _cmd_evidence(self, args):
        if not args:
            self.console.print('[dim]Usage: evidence <risk_key>[/dim]')
            return
        key = args[0]
        try:
            result = self.sdk.risks.get(key, evidence=True)
            self._render_evidence(result)
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_report(self, args):
        if not args:
            self.console.print('[dim]Usage: report <generate|validate> [options][/dim]')
            return
        subcmd = args[0].lower()
        if subcmd == 'generate':
            self._report_generate(args[1:])
        elif subcmd == 'validate':
            self._report_validate(args[1:])
        else:
            self.console.print(f'[dim]Unknown report subcommand: {subcmd}[/dim]')

    def _report_generate(self, args):
        body = {'format': 'pdf'}
        i = 0
        while i < len(args):
            if args[i] == '--title' and i + 1 < len(args):
                body['title'] = args[i + 1]; i += 2
            elif args[i] == '--client' and i + 1 < len(args):
                body['client'] = args[i + 1]; i += 2
            elif args[i] == '--risks' and i + 1 < len(args):
                body['risks'] = args[i + 1]; i += 2
            elif args[i] == '--group-by-phase':
                body['groupByPhase'] = True; i += 1
            elif args[i] == '--format' and i + 1 < len(args):
                body['format'] = args[i + 1]; i += 2
            else:
                i += 1
        try:
            result = self.sdk.post('export/report', body)
            self.console.print(f'[success]Report generated[/success]')
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]Report generation failed: {e}[/error]')

    def _report_validate(self, args):
        body = {}
        i = 0
        while i < len(args):
            if args[i] == '--risks' and i + 1 < len(args):
                body['risks'] = args[i + 1]; i += 2
            elif args[i] == '--include-narratives':
                body['includeNarratives'] = True; i += 1
            else:
                i += 1
        try:
            result = self.sdk.post('validate-report', body)
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]Validation failed: {e}[/error]')
