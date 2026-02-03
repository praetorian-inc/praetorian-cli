# praetorian_cli/handlers/workflow.py
"""CLI handlers for agent workflows.

Provides `praetorian chariot agent workflow` subcommands for running
LiteLLM-based agent workflows.
"""
import json
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


def _get_default_model() -> str:
    """Get default model based on available API key."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic/claude-sonnet-4-20250514"
    elif os.environ.get("OPENAI_API_KEY"):
        return "openai/gpt-4o"
    elif os.environ.get("GEMINI_API_KEY"):
        return "gemini/gemini-1.5-pro"
    elif os.environ.get("AZURE_API_KEY"):
        return "azure/gpt-4o"
    return "anthropic/claude-sonnet-4-20250514"  # Default


@agent.group()
def workflow():
    """Run multi-agent workflows for security research.

    Workflows chain multiple AI agents together for complex tasks like
    CVE research, Nuclei template generation, and template refinement.

    \b
    Available workflows:
        exploit   - Generate Nuclei exploit templates from CVE IDs
        generate  - Generate Nuclei detection templates from CVE IDs
        refine    - Refine existing Nuclei templates

    \b
    Required environment variable (one of):
        ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, AZURE_API_KEY

    \b
    Example:
        praetorian chariot agent workflow exploit --cve-id CVE-2024-1234
    """
    pass


@workflow.command("list")
def list_workflows():
    """List all available workflows.

    Shows registered workflows with their descriptions and required arguments.
    """
    # Import here to avoid circular imports and trigger registration
    from praetorian_chariot.agent_framework import list_workflows as get_all_workflows
    from praetorian_chariot.capabilities import workflows as _  # noqa: F401 - triggers registration

    all_workflows = get_all_workflows()

    if not all_workflows:
        click.echo("No workflows registered.")
        return

    click.echo("Available workflows:\n")
    for wf in all_workflows:
        click.echo(f"  {wf.cli_name}")
        click.echo(f"    {wf.description}")
        if wf.required_args:
            click.echo(f"    Required: {', '.join(wf.required_args)}")
        if wf.optional_args:
            click.echo(f"    Optional: {', '.join(wf.optional_args)}")
        click.echo()


@workflow.command("exploit")
@click.option("--cve-id", required=True, help="CVE identifier (e.g., CVE-2024-1234)")
@click.option("--output-dir", "-o", help="Directory for output artifacts (auto-generated if not specified)")
@click.option("--model", "-m", help="LLM model to use (e.g., openai/gpt-4o)")
def exploit_workflow(cve_id: str, output_dir: str | None, model: str | None):
    """Generate Nuclei exploit templates from CVE IDs.

    This workflow chains 3 agents:
    1. ExploitResearchAgent - Researches CVE exploitation vectors
    2. TechnologyAnalysisAgent - Analyzes affected technologies
    3. ExploitTemplateGeneratorAgent - Generates Nuclei template

    \b
    Example:
        praetorian chariot agent workflow exploit --cve-id CVE-2024-1234
        praetorian chariot agent workflow exploit --cve-id CVE-2024-1234 -o ./output
        praetorian chariot agent workflow exploit --cve-id CVE-2024-1234 -m openai/gpt-4o
    """
    _run_workflow("exploit", {"cve_id": cve_id}, output_dir, model)


@workflow.command("generate")
@click.option("--cve-id", required=True, help="CVE identifier (e.g., CVE-2024-1234)")
@click.option("--output-dir", "-o", help="Directory for output artifacts")
@click.option("--model", "-m", help="LLM model to use")
@click.option("--template-type", "-t", default="detection", help="Template type: detection or exploitation")
def generate_workflow(cve_id: str, output_dir: str | None, model: str | None, template_type: str):
    """Generate Nuclei detection templates from CVE IDs.

    This workflow chains 2 agents:
    1. CVEResearchAgent - Researches CVE details
    2. TemplateGeneratorAgent - Generates Nuclei template

    \b
    Example:
        praetorian chariot agent workflow generate --cve-id CVE-2024-1234
        praetorian chariot agent workflow generate --cve-id CVE-2024-1234 -t exploitation
    """
    _run_workflow("generate", {"cve_id": cve_id, "template_type": template_type}, output_dir, model)


@workflow.command("refine")
@click.option("--cve-id", required=True, help="CVE identifier (e.g., CVE-2024-1234)")
@click.option("--template", "-t", required=True, type=click.Path(exists=True), help="Path to existing template file")
@click.option("--output-dir", "-o", help="Directory for output artifacts")
@click.option("--model", "-m", help="LLM model to use")
@click.option("--prompt", "-p", default="", help="Refinement guidance (e.g., 'reduce false positives')")
def refine_workflow(cve_id: str, template: str, output_dir: str | None, model: str | None, prompt: str):
    """Refine existing Nuclei templates with CVE research.

    This workflow chains 2 agents:
    1. CVEResearchAgent - Researches CVE with refinement context
    2. TemplateRefinerAgent - Refines the existing template

    \b
    Example:
        praetorian chariot agent workflow refine --cve-id CVE-2024-1234 -t template.yaml
        praetorian chariot agent workflow refine --cve-id CVE-2024-1234 -t template.yaml -p "reduce false positives"
    """
    # Read existing template
    template_content = Path(template).read_text()

    _run_workflow(
        "refine",
        {"cve_id": cve_id, "existing_template": template_content, "refinement_prompt": prompt},
        output_dir,
        model,
    )


def _run_workflow(cli_name: str, workflow_input: dict, output_dir: str | None, model: str | None):
    """Execute a workflow with progress output.

    Args:
        cli_name: The workflow CLI name (e.g., "exploit")
        workflow_input: Input dict for workflow.run()
        output_dir: Optional output directory
        model: Optional model override
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
    meta = get_workflow(cli_name)
    if not meta:
        click.echo(f"Error: Unknown workflow '{cli_name}'", err=True)
        sys.exit(1)

    # Determine model
    actual_model = model or _get_default_model()

    # Create artifact manager
    identifier = workflow_input.get("cve_id", "workflow")
    artifacts = ArtifactManager(
        workflow_name=cli_name,
        identifier=identifier,
        output_dir=output_dir,
    )

    # Save metadata
    artifacts.save_metadata(
        cve_id=workflow_input.get("cve_id"),
        model=actual_model,
        workflow=cli_name,
        api_key_source=api_key_var,
    )

    # Create workflow
    click.echo(f"Running workflow: {meta.description}")
    click.echo(f"Model: {actual_model}")
    click.echo(f"Output: {artifacts.output_dir}\n")

    try:
        # Build agent configs with model
        from praetorian_chariot.agent_framework import AgentConfig

        # Create config with specified model
        config = AgentConfig(model=actual_model)

        # Map config to all agents by class name
        agent_configs = {}
        for step in meta.workflow_class.pipeline:
            agent_configs[step.agent.__name__] = config

        workflow = WorkflowFactory.create(meta.workflow_class, agent_configs=agent_configs)

        # Execute with progress
        total_steps = len(workflow.steps)
        for i, step in enumerate(workflow.steps, 1):
            click.echo(f"  [{i}/{total_steps}] {step.name.capitalize()}...", nl=False)
            artifacts.log(f"Starting step: {step.name}")

        # Actually run the workflow
        result = workflow.run(workflow_input)

        # Mark all complete (we can't do real progress without callbacks)
        click.echo("\r" + " " * 50 + "\r", nl=False)  # Clear line
        for i, step in enumerate(workflow.steps, 1):
            click.echo(f"  [{i}/{total_steps}] {step.name.capitalize()}... ✓")

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
