import argparse
from pathlib import Path

from .config import AppConfig, load_dotenv
from .providers import build_provider
from .workflow import load_case, run_refund_workflow


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the agent-consistency refund workflow demo.",
    )
    parser.add_argument(
        "--input",
        default="samples/inputs/happy_path.json",
        help="Path to a scenario JSON file.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional .env file path.",
    )
    args = parser.parse_args()

    load_dotenv(args.env_file)
    config = AppConfig.from_env()
    provider = build_provider(config)
    case = load_case(args.input)
    result = run_refund_workflow(case, config=config, provider=provider)

    print(f"Workflow result: {result.status.upper()}")
    print(f"Run id: {result.run_id}")
    print(f"Provider: {provider.name}")
    print(f"Receipts: {len(result.receipts)}")
    print(f"Report: {Path(result.report_path)}")
    print(f"Receipt log: {Path(result.receipts_path)}")
    if result.failure:
        print(f"Failure: {result.failure['type']}: {result.failure['message']}")
    if result.final_message:
        print(f"Customer message id: {result.final_message['message_id']}")

    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
