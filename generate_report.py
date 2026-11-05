"""Generate a two-page scouting report from a report YAML and a Wyscout export.

Usage:
    python generate_report.py reports/example_cb.yaml data/demo_wyscout_export.xlsx
    python generate_report.py reports/my_player.yaml exports/serbia_2026.xlsx --theme paper
"""

from __future__ import annotations

import argparse
import sys

from scout_report.render import render


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", help="Report YAML with player details and scouting notes")
    parser.add_argument("export", help="Wyscout export (.xlsx or .csv) of the comparison league")
    parser.add_argument("--theme", default="night", choices=["night", "paper"])
    parser.add_argument("--out", default=None, help="Output folder (default: output/<player-slug>)")
    parser.add_argument("--scale", type=float, default=2.0, help="PNG pixel density (2 = 3840 x 2160)")
    parser.add_argument("--formats", default="png,pdf", help="Comma-separated: png,pdf")
    args = parser.parse_args()

    print(f"Rendering {args.report}")
    render(args.report, args.export, args.out, args.theme, args.scale, tuple(args.formats.split(",")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
