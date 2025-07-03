import argparse

parser = argparse.ArgumentParser("localbot")
parser.add_argument("--verbose", help="Verbose logging", action="store_true")
parser.add_argument("--token", help="Auth token", type=str, default=None)
