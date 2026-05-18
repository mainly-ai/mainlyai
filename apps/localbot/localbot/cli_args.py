# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse

parser = argparse.ArgumentParser("localbot")
parser.add_argument("--verbose", help="Verbose logging", action="store_true")
parser.add_argument("--token", help="Auth token", type=str, default=None)
parser.add_argument("--crg_id", help="CRG ID", type=int, default=None)
parser.add_argument(
    "--skip-hw-check",
    help="Skip hardware reporting stage on startup",
    action="store_true",
)
