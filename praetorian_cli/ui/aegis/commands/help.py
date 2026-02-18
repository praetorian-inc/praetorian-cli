from rich.table import Table
from rich.box import MINIMAL
from ..constants import DEFAULT_COLORS





def handle_help(menu, args):
    """Show help for commands or a specific command."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    if args and args[0] in ['ssh', 'cp', 'list', 'info', 'job', 'schedule', 'set']:
        menu.console.print(f"\nHelp for '{args[0]}' command - see main help for details\n")
        menu.pause()
        return

    commands_table = Table(
        show_header=True,
        header_style=f"bold {colors['primary']}",
        border_style=colors['dim'],
        box=MINIMAL,
        show_lines=False,
        padding=(0, 2),
        pad_edge=False
    )

    commands_table.add_column("COMMAND", style=f"bold {colors['success']}", min_width=20, no_wrap=True)
    commands_table.add_column("DESCRIPTION", style="white", no_wrap=False)

    commands_table.add_row("set <id>", "Select an agent by number, client_id, or hostname")
    commands_table.add_row("list [--all]", "List online agents (--all shows offline too)")
    commands_table.add_row("ssh [options]", "SSH to selected agent (use 'ssh --help' for options)")
    commands_table.add_row("cp <src> <dst>", "Copy files to/from agent (use ':' for remote paths)")
    commands_table.add_row("info [--raw]", "Show detailed information for selected agent")
    commands_table.add_row("job list", "List recent jobs for selected agent")
    commands_table.add_row("job capabilities [--details]", "List available capabilities")
    commands_table.add_row("job run <capability>", "Run capability on selected agent")
    commands_table.add_row("schedule list", "List scheduled jobs")
    commands_table.add_row("schedule add", "Create a new scheduled job")
    commands_table.add_row("schedule view <id>", "View schedule details")
    commands_table.add_row("schedule edit <id>", "Edit a schedule")
    commands_table.add_row("schedule delete <id>", "Delete a schedule")
    commands_table.add_row("schedule pause/resume <id>", "Pause or resume a schedule")
    commands_table.add_row("reload", "Refresh agent list from server")
    commands_table.add_row("help [command]", "Show this help or command-specific help")
    commands_table.add_row("clear", "Clear terminal screen")
    commands_table.add_row("quit / exit", "Exit the interface")

    menu.console.print()
    menu.console.print("  Available Commands")
    menu.console.print()
    menu.console.print(commands_table)

    examples_table = Table(
        show_header=True,
        header_style=f"bold {colors['warning']}",
        border_style=colors['dim'],
        box=MINIMAL,
        show_lines=False,
        padding=(0, 2),
        pad_edge=False
    )

    examples_table.add_column("EXAMPLE", style=f"bold {colors['accent']}", min_width=25, no_wrap=True)
    examples_table.add_column("DESCRIPTION", style=f"{colors['dim']}", no_wrap=False)

    examples_table.add_row("set 1", "Select first agent")
    examples_table.add_row("set abc", "Select agent by hostname")
    examples_table.add_row("ssh -D 1080", "SSH with SOCKS proxy on port 1080")
    examples_table.add_row("cp ./file.txt :/tmp/file.txt", "Upload file to agent")
    examples_table.add_row("cp :/etc/hosts ./hosts", "Download file from agent")
    examples_table.add_row("list --all", "Show all agents including offline")
    examples_table.add_row("job list", "List recent jobs")
    examples_table.add_row("job capabilities", "List available capabilities")
    examples_table.add_row("job caps --details", "Show full capability descriptions")
    examples_table.add_row("job run windows-enum", "Run capability on selected agent")
    examples_table.add_row("schedule list", "List all scheduled jobs")
    examples_table.add_row("schedule add", "Create a new scheduled job")
    examples_table.add_row("schedule view abc123", "View schedule details")
    examples_table.add_row("schedule pause abc123", "Pause a scheduled job")
    examples_table.add_row("info", "Show agent details")
    examples_table.add_row("info --raw", "Show raw agent data (JSON format)")

    menu.console.print()
    menu.console.print("  Examples")
    menu.console.print()
    menu.console.print(examples_table)
    menu.console.print()
    menu.pause()


def complete(menu, text, tokens):
    # Suggest commands after 'help '
    return [c for c in menu.commands if c.startswith(text)]
