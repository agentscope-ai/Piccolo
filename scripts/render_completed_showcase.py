#!/usr/bin/env python3
"""Render the three active completed-game cards through the complete timeline exporter."""
import argparse
from pathlib import Path
from render_showcase import ROOT, render

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    for slug in ('merge-2048', 'sokoban', 'tetris'):
        render(args.root, slug)
