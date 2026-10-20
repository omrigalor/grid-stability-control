import argparse
import json

from .model import simulate, summarize


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a multi-area frequency-control study")
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--loss", type=float, default=0.12)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-battery", action="store_true")
    args = parser.parse_args()
    states = simulate(args.seconds, args.seed, not args.no_battery, loss_pu=args.loss)
    print(json.dumps(summarize(states), indent=2))


if __name__ == "__main__":
    main()
