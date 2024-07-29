import importlib
import sys
from functools import wraps
from inspect import signature
from io import StringIO
from types import ModuleType

import click


def handle_api_error(func):
    @wraps(func)
    def handler(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            click.secho(e.args[0], fg='red')

    return handler


def cli_handler(func):
    func = click.pass_obj(func)
    func = handle_api_error(func)
    return func


def list_options(filter_name):
    def decorator(func):
        func = cli_handler(func)
        func = click.option('-f', '--filter', default="", help=f"Filter by {filter_name}")(func)
        func = click.option('-d', '--details', is_flag=True, default=False, help="Show detailed information")(
            func)
        func = page_options(func)
        func = plugins(func)
        return func

    return decorator


def page_options(func):
    func = click.option('-o', '--offset', default='', help='List results from an offset')(func)
    func = click.option('-p', '--page', type=click.Choice(('no', 'interactive', 'all')), default='no',
                        help="Pagination mode. 'all' pages up to 100 pages. Default: 'no'")(func)

    return func


def plugins(f):
    @click.option('--plugin', help="Specify a plugin to process the output")
    @wraps(f)
    def decorated_function(*args, plugin=None, **kwargs):
        if plugin is None:
            return f(*args, **kwargs)

        if 'page' in kwargs and kwargs['page'] == 'interactive':
            click.echo("Scripts can only be used with 'no' or 'all' pagination mode.", err=True)
            exit(1)

        old_stdout = sys.stdout
        sys.stdout = my_stdout = StringIO()

        try:
            result = f(*args, **kwargs)
            output = my_stdout.getvalue().rstrip()
        finally:
            sys.stdout = old_stdout

        if plugin:
            process_with_plugin(plugin, output, kwargs)
        else:
            click.echo(output)

        return result

    return decorated_function


def process_with_plugin(plugin_name, output, cli_kwargs):
    plugin_module = import_plugin(plugin_name)
    if not plugin_module:
        return

    if (hasattr(plugin_module, 'process') and callable(plugin_module.process)
            and len(signature(plugin_module.__dict__['process']).parameters) == 4):
        ctx = click.get_current_context()
        controller = ctx.obj
        if ctx.command.name == 'search':
            cmd = dict(product=ctx.parent.command.name, action=ctx.command.name, type=None)
        else:
            cmd = dict(product=ctx.parent.parent.command.name, action=ctx.parent.command.name,
                       type=ctx.command.name)

        plugin_module.process(controller, cmd, cli_kwargs, output)
    else:
        click.echo(f"The plugin {plugin_name} does not have a 'process' function that takes 4 arguments.", err=True)


def import_plugin(plugin_name):
    # try importing from the praetorian_cli/scripts package
    try:
        return importlib.import_module(f'.plugins.scripts.{plugin_name}', 'praetorian_cli')
    except ImportError:
        # try importing from the current directory as a raw script
        try:
            return load_raw_script(plugin_name)
        except Exception as e:
            click.echo(f'Error importing plugin {plugin_name}: {e}', err=True)
            return None


def load_raw_script(path):
    module = ModuleType('cli-plugin-script')
    module.__file__ = path
    with open(path, 'r') as code_file:
        exec(compile(code_file.read(), path, 'exec'), module.__dict__)
    sys.modules['cli-plugin-script"'] = module
    return module
