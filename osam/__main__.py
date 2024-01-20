import datetime
import json
import sys

import click
import numpy as np
import PIL.Image

from osam import _humanize
from osam import _jsondata
from osam import _tabulate
from osam import logger
from osam import models
from osam.prompt import Prompt


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
def cli():
    pass


@cli.command()
@click.argument("subcommand", required=False, type=str)
@click.pass_context
def help(ctx, subcommand):
    if subcommand is None:
        click.echo(cli.get_help(ctx))
        return

    subcommand_obj = cli.get_command(ctx, subcommand)
    if subcommand_obj is None:
        click.echo(f"Unknown subcommand {subcommand!r}", err=True)
        click.echo(cli.get_help(ctx))
    else:
        click.echo(subcommand_obj.get_help(ctx))


@cli.command(help="list available models")
@click.option("--all", "-a", "show_all", is_flag=True, help="show all models")
def list(show_all):
    rows = []
    for model in models.MODELS:
        size = model.get_size()
        modified_at = model.get_modified_at()

        if not show_all and (size is None or modified_at is None):
            continue

        rows.append(
            [
                model.name,
                model.get_id(),
                "<not pulled>" if size is None else _humanize.naturalsize(size),
                "<not pulled>"
                if modified_at is None
                else _humanize.naturaltime(
                    datetime.datetime.fromtimestamp(modified_at)
                ),
            ]
        )
    print(_tabulate.tabulate(rows, headers=["NAME", "ID", "SIZE", "MODIFIED"]))


@cli.command(help="pull model")
@click.argument("model_name", metavar="model", type=str)
def pull(model_name):
    for cls in models.MODELS:
        if cls.name == model_name:
            break
    else:
        logger.error(f"Model {model_name} not found.")
        sys.exit(1)

    logger.info(f"Pulling {model_name!r}...")
    cls.pull()
    logger.info(f"Pulled {model_name!r}")


@cli.command(help="remove model")
@click.argument("model_name", metavar="model", type=str)
def rm(model_name):
    for cls in models.MODELS:
        if cls.name == model_name:
            break
    else:
        logger.error(f"Model {model_name} not found.")
        sys.exit(1)

    logger.info(f"Removing {model_name!r}...")
    cls.remove()
    logger.info(f"Removed {model_name!r}")


@cli.command(help="run model")
@click.argument("model_name", metavar="model", type=str)
@click.option(
    "--image",
    "image_path",
    type=click.Path(exists=True),
    help="image path",
    required=True,
)
@click.option("--prompt", type=json.loads, help="prompt", required=True)
def run(model_name, image_path, prompt):
    for cls in models.MODELS:
        if cls.name == model_name:
            break
    else:
        logger.error(f"Model {model_name} not found.")
        sys.exit(1)

    if not ("points" in prompt and "point_labels" in prompt):
        logger.error("'points' and 'point_labels' must be specified in prompt.")
        sys.exit(1)
    if len(prompt["points"]) != len(prompt["point_labels"]):
        logger.error("Length of 'points' and 'point_labels' must be same.")
        sys.exit(1)

    model = cls()
    logger.debug(f"Loaded {model_name!r}: {model}")

    image = np.asarray(PIL.Image.open(image_path))
    logger.debug(f"Loaded {image_path!r}: {image.shape}, {image.dtype}")

    image_embedding = model.encode_image(image)
    logger.debug(
        f"Encoded image: {image_embedding.embedding.shape}, "
        f"{image_embedding.embedding.dtype}"
    )

    mask = model.generate_mask(
        image_embedding=image_embedding,
        prompt=Prompt(points=prompt["points"], point_labels=prompt["point_labels"]),
    )
    print(_jsondata.ndarray_to_b64data(mask.astype(np.uint8) * 255), end="")


if __name__ == "__main__":
    cli()
