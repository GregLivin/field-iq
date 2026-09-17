from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from pipeline.collect_nflverse import collect_nflverse
from pipeline.collect_weather import collect_weather
from pipeline.train_models import train_and_predict


def run_daily(skip_weather: bool = False) -> dict[str, object]:
    report: dict[str, object] = {
        "startedAt": datetime.now(UTC).isoformat(),
        "nflverse": collect_nflverse(),
    }
    if not skip_weather:
        report["weather"] = collect_weather()
    report["model"] = train_and_predict()
    report["finishedAt"] = datetime.now(UTC).isoformat()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the complete FieldIQ daily pipeline")
    parser.add_argument("--skip-weather", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_daily(args.skip_weather), indent=2))

