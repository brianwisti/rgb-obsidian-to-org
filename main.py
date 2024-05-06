"""
Convert an Obsidian vault to org-roam.

Copyright 2024 Brian Wisti

This file is part of rgb-obsidian-to-org.

rgb-obsidian-to-org is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
import logging
import multiprocessing as mp
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter
import pypandoc
import rich
from rich.columns import Columns
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.syntax import Syntax
from slugify import slugify

logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])

CONTENT_SUFFIXES = [".md"]
ASSET_SUFFIXES = [".jpg", ".png"]


@dataclass
class NoteConverter:
    input_dir: Path
    output_dir: Path
    source: Path
    md_note: frontmatter.Post = field(init=False)
    slug: str = field(init=False)
    _org_content: str = field(init=False)

    def __post_init__(self):
        self.md_note = frontmatter.loads(self.source.read_text(encoding="utf-8"))
        self.slug = slugify(self.source.stem, separator="_")
        self._org_content = ""

    @property
    def meta(self):
        """Return the note metadata."""
        return self.md_note.metadata

    @property
    def org_id(self):
        return self.slug

    @property
    def org_path(self):
        timestamp = self.meta["created"].strftime("%Y%m%d%H%M%S")

        return f"{timestamp}-{self.slug}.org"

    @property
    def title(self):
        """Return the title associated with this note."""
        if title := self.md_note.get("title"):
            return title

        return self.source.stem

    def as_org(self):
        """Return the org file version of this note."""
        org_content = self.org_content()
        frontmatter = "\n".join([f"#+{k}: {v}" for k, v in self.get_org_meta().items()])

        return (
            f":PROPERTIES:\n:ID: {self.org_id}\n:END:\n{frontmatter}\n\n{org_content}"
        )

    def get_org_meta(self):
        """Return the dictionary of metadata needed for org-roam files."""
        section = self.source.relative_to(self.input_dir).parts[0]
        logging.debug("Section: %s", section)

        return {
            "title": self.title,
            "filetags": f":{section}:",
        }

    def org_content(self):
        if not self._org_content:
            self._org_content = self._generate_org_content()

        return self._org_content

    def get_org_roam_link(self, link_text: str = None):
        if link_text is None:
            link_text = self.title

        return f"[[id:{self.org_id}][{link_text}]]"

    def _generate_org_content(self):
        cache_file = Path(f"cache/pandoc/") / self.org_path

        if (
            cache_file.is_file()
            and cache_file.stat().st_mtime > self.source.stat().st_mtime
        ):
            transformed_md = cache_file.read_text(encoding="utf-8")
        else:
            transformed_md = pypandoc.convert_text(
                self.md_note.content,
                "org",
                format="markdown+wikilinks_title_after_pipe",
                extra_args=["--wrap=none"],
            )
            cache_file.write_text(self._org_content, encoding="utf-8")

        return transformed_md


VaultMap = dict[Path, NoteConverter]
AssetMap = dict[Path, Path]


@dataclass
class VaultConverter:
    """Knows about Obsidian vault files and where to find them."""

    vault_map: VaultMap
    asset_map: AssetMap
    output_dir: Path

    def from_stem(self, stem: str):
        """
        Get the note with corresponding file stem.

        Raises an exception if there are no matches.

        Raises an exception if there is more than one match.
        """
        matches = [path for path in self.vault_map if path.stem == stem]

        if not matches:
            logging.debug("No note stem matched '%s'", stem)
            return

        if len(matches) > 1:
            logging.error(
                "Excess stem matches for '%s': %s", stem, [path for path in matches]
            )
            raise ValueError("Too many stem matches found")

        return self.vault_map[matches[0]]

    def ensure_link(self, requested_link: str, link_text: str = None):
        base = requested_link.split("/")[-1]

        if note := self.from_stem(base):
            return note.get_org_roam_link(link_text)

        link_path = Path(requested_link)

        if asset_path := self.asset_map.get(link_path):
            output_path = self.output_dir / link_path

            if not output_path.is_file():
                logging.info("Copying asset file: %s", asset_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(asset_path, output_path)

            return f"[[{link_path}]]"

        logging.warning("Requested link is not in vault, returning placeholder: %s")

        if link_text:
            return f"/{link_text}/"

        return f"/{requested_link}/"


def parse_commandline_arguments():
    """Parse the commandline arguments."""
    parser = argparse.ArgumentParser(
        description="""Convert your Obsidian vault to
                        Org-roam compatible org-files."""
    )
    parser.add_argument(
        "input_dir",
        help="Your Obsidian Vault (Remember to Backup)",
    )
    parser.add_argument(
        "output_dir", help="The Folder which The Org Files will Output To"
    )

    return parser.parse_args()


def main():
    """Convert contents of input_dir as org files to output_dir."""
    args = parse_commandline_arguments()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    logging.info("Read from: %s; write to: %s", input_dir, output_dir)
    console = Console()

    if not input_dir.exists():
        raise ValueError("Input dir does not exist")

    asset_map = {}
    vault_map = {}

    for path in input_dir.glob("**/*.*"):
        vault_path = path.relative_to(input_dir)

        if path.suffix in ASSET_SUFFIXES:
            logging.debug("Loaded asset: %s", vault_path)
            asset_map[vault_path] = path
            continue

        if path.suffix in CONTENT_SUFFIXES:
            if path.parent.stem.startswith("_"):
                continue

            if path.stem.startswith("_"):
                # Ignore meta sections for Obsidian and meta files for Hugo.
                continue

            if "/config/" in str(path):
                # Ignore config files, which were converted from Org anyways.
                continue

            note = NoteConverter(input_dir, output_dir, path)
            logging.debug("Loaded note: %s", note.title)
            vault_map[vault_path] = note

    vault = VaultConverter(vault_map, asset_map, output_dir)

    with mp.Pool(processes=mp.cpu_count()) as pool:
        pool.map(
            process_note,
            [(converter, vault) for converter in vault.vault_map.values()],
        )


def process_note(args):
    converter, vault = args
    logging.info("Processing note: %s", converter.source)
    org_path = vault.output_dir / converter.org_path
    org_content = converter.as_org()
    ORG_LINK = r"""
            \[
                \[file:
                    (?P<link> [^\]]+?)
                \]
                (?:
                    \[
                        (?P<title> [^\]]+?)
                    \]
                )?
            \]
    """
    org_link = re.compile(ORG_LINK, re.VERBOSE)

    def find_link(match):
        logging.debug("<Match: %r, groups=%r>", match.group(), match.groups())
        fallback = match.group()
        link_match = match.group("link")
        title = match.group("title")
        if link := vault.ensure_link(link_match, title):
            return link

        logging.warning("Using original fallback for link: %s", fallback)
        return fallback

    org_content = org_link.sub(find_link, org_content)
    org_path.write_text(org_content, encoding="utf-8")


if __name__ == "__main__":
    main()
