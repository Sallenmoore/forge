# src/forge/cli/label.py
import json as json_module

import click

from forge.cli._common import filter_json
from forge.cli._common import resolve as _resolve
from forge.translate import label_to_gh


@click.group()
def label():
    """Label subcommands."""


@label.command("list")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--json", "json_fields", default=None,
              help="Comma-separated gh-shape fields to emit as JSON")
@click.pass_context
def label_list(ctx, repo, json_fields):
    """List the repo's labels (every page)."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        rows = [label_to_gh(lbl)
                for lbl in client.paginate(f"/repos/{spec.owner}/{spec.repo}/labels")]
    finally:
        client.close()
    if json_fields:
        click.echo(json_module.dumps(filter_json(rows, json_fields, "label")))
        return
    for r in rows:
        click.echo("\t".join([r["name"], r["description"] or "", f"#{r['color']}"]))
