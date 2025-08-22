def handle_info(menu, args):
    """Show detailed information for the selected agent."""
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    try:
        menu.console.print(menu.selected_agent.to_detailed_string())
        menu.console.print()
        menu.pause()
    except Exception as e:
        menu.console.print(f"[red]Error getting agent info: {e}[/red]")
        menu.pause()


