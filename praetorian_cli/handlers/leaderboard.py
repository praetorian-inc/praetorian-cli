import sys
import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json


@chariot.group()
def leaderboard():
    """Leaderboard snapshots and weight configuration"""
    pass


@leaderboard.command('get')
@cli_handler
@praetorian_only
def get_leaderboard(chariot):
    """Get the current leaderboard snapshot"""
    print_json(chariot.leaderboard.get())


@leaderboard.command('get-weights')
@cli_handler
@praetorian_only
def get_weights(chariot):
    """Get leaderboard weight configuration"""
    print_json(chariot.leaderboard.get_weights())


@leaderboard.command('set-weights')
@cli_handler
@praetorian_only
def set_weights(chariot):
    """Update leaderboard weights (reads JSON from stdin)

    Stdin JSON should be a map of weight names to numeric values.
    """
    raw = sys.stdin.read().strip()
    if not raw:
        raise click.UsageError('Weights JSON is required via stdin')
    weights = json.loads(raw)
    print_json(chariot.leaderboard.set_weights(weights))
