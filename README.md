# Random Geekery Obsidian to Org Converter

Convert an Obsidian Markdown vault to an org-roam wiki.

## CAVEAT

An exploratory experiment. Untested, unsafe, etc etc. It barely works on my
machine. I better push this somewhere in case I accidentally melt my hard
drive.

I would be surprised if this melted your hard drive, but we live in a universe
of infinite possibility.

Meanwhile I'll try to make everything more generically useful.

## Tools Used

- just
- pandoc
- Python
- GNU Emacs

## Workflow

Describing the state of things at the end of the experiment. I'll update as the
process improves.

First, ensure you have the tools. Details of this will vary by platform.

Then install the Python dependencies.

``` sh
pip install -r requirements.txt
```

Edit the `pull` task in the justfile to reflect your vault location.

Pull and process your notes, crossing your fingers the whole time.

``` sh
just run
```

This copies note files to `input/` and transforms *those* files into Org format
with Pandoc, updating file properties and pulling asset files as needed.

Invoking `pandoc` is one file at a time in this incarnation, and takes a while
for large vaults. Raw Pandoc output is cached to disk, dramatically speeding up
  the process for followup runs.

## Inspiration

- [rberaldo/obsidian-to-org.py](https://gist.github.com/rberaldo/2a3bd82d5ed4bc39fee7e8ff4a6242b2)
- [jml/obsidian-to-org](https://github.com/jml/obsidian-to-org)

## LICENSE

*Since jml/obsidian-to-org went with GPL-v3 I will too*

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
