# praetorian_cli/handlers/workflow.py
"""CLI handlers for agent workflows.

Provides `praetorian chariot agent workflow` subcommands for running
LiteLLM-based agent workflows using a generic, scalable approach.

Commands:
    list [--filter PATTERN]     - List available workflows
    info <name>                 - Show workflow parameters and usage
    run <name> [key=value ...]  - Run a workflow with dynamic parameters
"""
import fnmatch
import os
import sys
from pathlib import Path

import click

from praetorian_cli.handlers.agent import agent


def _check_llm_api_key() -> str | None:
    """Check for LLM API key in environment.

    Returns:
        Name of the found API key env var, or None if not found.
    """
    for env_var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "AZURE_API_KEY"]:
        if os.environ.get(env_var):
            return env_var
    return None


def _parse_key_value_args(args: tuple[str, ...]) -> dict[str, str]:
    """Parse key=value arguments into a dictionary.

    Args:
        args: Tuple of strings in "key=value" format

    Returns:
        Dictionary of parsed key-value pairs

    Raises:
        click.BadParameter: If an argument is not in key=value format
    """
    result = {}
    for arg in args:
        if "=" not in arg:
            raise click.BadParameter(
                f"Invalid argument '{arg}'. Use key=value format (e.g., cve_id=CVE-2024-1234)"
            )
        key, value = arg.split("=", 1)
        if not key:
            raise click.BadParameter(f"Empty key in argument '{arg}'")
        result[key] = value
    return result


@agent.group()
def workflow():
    """Run multi-agent workflows for security research.

    Workflows chain multiple AI agents together for complex tasks like
    CVE research, Nuclei template generation, and template refinement.

    \b
    Commands:
        list              List available workflows
        info <name>       Show workflow parameters and usage
        run <name> ...    Run a workflow with parameters

    \b
    Required environment variable (one of):
        ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, AZURE_API_KEY

    \b
    Examples:
        praetorian chariot agent workflow list
        praetorian chariot agent workflow info exploit
        praetorian chariot agent workflow run exploit cve_id=CVE-2024-1234
    """
    pass


@workflow.command("list")
@click.option("--filter", "-f", "pattern", default=None, help="Filter workflows by name pattern (e.g., 'cve*')")
def list_workflows(pattern: str | None):
    """List all available workflows.

    Shows registered workflows with their descriptions.
    Use --filter to filter by name pattern (supports wildcards).

    \b
    Examples:
        praetorian chariot agent workflow list
        praetorian chariot agent workflow list --filter "cve*"
        praetorian chariot agent workflow list -f "*template*"
    """
    # Import here to avoid circular imports and trigger registration
    from praetorian_chariot.agent_framework import list_workflows as get_all_workflows
    from praetorian_chariot.capabilities import workflows as _  # noqa: F401 - triggers registration

    all_workflows = get_all_workflows()

    if not all_workflows:
        click.echo("No workflows registered.")
        return

    # Apply filter if provided
    if pattern:
        all_workflows = [wf for wf in all_workflows if fnmatch.fnmatch(wf.cli_name, pattern)]
        if not all_workflows:
            click.echo(f"No workflows matching pattern '{pattern}'.")
            return

    click.echo("Available workflows:\n")
    for wf in all_workflows:
        click.echo(f"  {wf.cli_name}")
        click.echo(f"    {wf.description}")
    click.echo(f"\nUse 'praetorian chariot agent workflow info <name>' for parameter details.")


@workflow.command("info")
@click.argument("name")
def workflow_info(name: str):
    """Show detailed information about a workflow.

    Displays the workflow's description, required parameters,
    optional parameters, and usage examples.

    \b
    Example:
        praetorian chariot agent workflow info exploit
    """
    from praetorian_chariot.agent_framework import get_workflow
    from praetorian_chariot.capabilities import workflows as _  # noqa: F401

    meta = get_workflow(name)
    if not meta:
        click.echo(f"Error: Unknown workflow '{name}'", err=True)
        click.echo("Use 'praetorian chariot agent workflow list' to see available workflows.", err=True)
        sys.exit(1)

    click.echo(f"\nWorkflow: {meta.cli_name}")
    click.echo(f"Description: {meta.description}")

    click.echo("\nRequired parameters:")
    if meta.required_args:
        for arg in meta.required_args:
            help_text = meta.arg_help.get(arg, "No description")
            click.echo(f"  {arg}: {help_text}")
    else:
        click.echo("  (none)")

    click.echo("\nOptional parameters:")
    if meta.optional_args:
        for arg in meta.optional_args:
            help_text = meta.arg_help.get(arg, "No description")
            click.echo(f"  {arg}: {help_text}")
    else:
        click.echo("  (none)")

    # Build example command
    example_args = []
    for arg in meta.required_args:
        if arg == "cve_id":
            example_args.append("cve_id=CVE-2024-1234")
        elif arg == "template":
            example_args.append("template=./template.yaml")
        else:
            example_args.append(f"{arg}=<value>")

    click.echo(f"\nUsage:")
    click.echo(f"  praetorian chariot agent workflow run {name} {' '.join(example_args)}")


@workflow.command("run")
@click.argument("name")
@click.argument("params", nargs=-1)
@click.option("--output-dir", "-o", help="Directory for output artifacts (auto-generated if not specified)")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to YAML config file for LLM settings")
def run_workflow(name: str, params: tuple[str, ...], output_dir: str | None, config: str | None):
    """Run a workflow with the specified parameters.

    Parameters are passed as key=value pairs. Use 'info <name>' to see
    what parameters a workflow requires.

    \b
    Examples:
        praetorian chariot agent workflow run exploit cve_id=CVE-2024-1234
        praetorian chariot agent workflow run generate cve_id=CVE-2024-1234 template_type=detection
        praetorian chariot agent workflow run refine cve_id=CVE-2024-1234 template=./existing.yaml
        praetorian chariot agent workflow run exploit cve_id=CVE-2024-1234 -c ./config.yaml -o ./output
    """
    # Check for API key
    api_key_var = _check_llm_api_key()
    if not api_key_var:
        click.echo("Error: No LLM API key found in environment.", err=True)
        click.echo("Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, AZURE_API_KEY", err=True)
        sys.exit(1)

    # Import workflow components
    from praetorian_chariot.agent_framework import (
        WorkflowFactory,
        get_workflow,
        ArtifactManager,
    )
    from praetorian_chariot.capabilities import workflows as _  # noqa: F401

    # Get workflow metadata
    meta = get_workflow(name)
    if not meta:
        click.echo(f"Error: Unknown workflow '{name}'", err=True)
        click.echo("Use 'praetorian chariot agent workflow list' to see available workflows.", err=True)
        sys.exit(1)

    # Parse key=value parameters
    try:
        workflow_input = _parse_key_value_args(params)
    except click.BadParameter as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)

    # Validate required parameters
    missing_args = []
    for required_arg in meta.required_args:
        if required_arg not in workflow_input:
            missing_args.append(required_arg)

    if missing_args:
        click.echo(f"Error: Missing required parameters: {', '.join(missing_args)}", err=True)
        click.echo(f"\nUse 'praetorian chariot agent workflow info {name}' to see required parameters.", err=True)
        sys.exit(1)

    # Handle special parameters that need file reading
    if "template" in workflow_input:
        template_path = Path(workflow_input["template"])
        if not template_path.exists():
            click.echo(f"Error: Template file not found: {template_path}", err=True)
            sys.exit(1)
        # Read template content and store as existing_template
        workflow_input["existing_template"] = template_path.read_text()

    # Create artifact manager
    identifier = workflow_input.get("cve_id", "workflow")
    artifacts = ArtifactManager(
        workflow_name=name,
        identifier=identifier,
        output_dir=output_dir,
    )

    # Save metadata
    artifacts.save_metadata(
        cve_id=workflow_input.get("cve_id"),
        config=config,
        workflow=name,
        api_key_source=api_key_var,
        parameters=workflow_input,
    )

    # Create workflow
    click.echo(f"Running workflow: {meta.description}")
    click.echo(f"Parameters: {workflow_input}")
    click.echo(f"Output: {artifacts.output_dir}\n")

    try:
        # Build agent configs
        from praetorian_chariot.agent_framework import AgentConfig

        # Create config - use provided config file or default
        if config:
            agent_config = AgentConfig.from_yaml(config)
        else:
            agent_config = AgentConfig()  # Uses defaults

        # Map config to all agents by class name
        agent_configs = {}
        for step in meta.workflow_class.pipeline:
            agent_configs[step.agent.__name__] = agent_config

        workflow_instance = WorkflowFactory.create(meta.workflow_class, agent_configs=agent_configs)

        # Execute with progress
        total_steps = len(workflow_instance.steps)
        for i, step in enumerate(workflow_instance.steps, 1):
            click.echo(f"  [{i}/{total_steps}] {step.name.capitalize()}...", nl=False)
            artifacts.log(f"Starting step: {step.name}")

        # Actually run the workflow
        result = workflow_instance.run(workflow_input)

        # Mark all complete
        click.echo("\r" + " " * 50 + "\r", nl=False)  # Clear line
        for i, step in enumerate(workflow_instance.steps, 1):
            click.echo(f"  [{i}/{total_steps}] {step.name.capitalize()}... done")

            # Save step output
            step_output = result.get(step.name)
            if step_output:
                artifacts.save_step_output(step.name, step_output)

        # Get final output
        final_output = result.get("final")

        # Save template if it has template_yaml attribute
        if hasattr(final_output, "template_yaml"):
            artifacts.save_template(final_output.template_yaml)
            click.echo(f"\nTemplate type: {getattr(final_output, 'template_type', 'unknown')}")
            click.echo(f"Confidence: {getattr(final_output, 'confidence', 'unknown')}")
            if hasattr(final_output, "notes") and final_output.notes:
                click.echo(f"Notes: {final_output.notes}")

        # Summary
        summary = artifacts.get_summary()
        click.echo(f"\nArtifacts saved to {summary['output_dir']}/")
        for f in summary["files"]:
            click.echo(f"  - {f}")

    except Exception as e:
        artifacts.log(f"Error: {e}", level="error")
        click.echo(f"\nError: {e}", err=True)
        click.echo(f"See {artifacts.log_path} for details", err=True)
        sys.exit(1)
