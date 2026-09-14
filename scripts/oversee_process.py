import argparse
import subprocess

from config import (
    NOTION_DATA_FILE,
    NOTION_DATA_PROD_FILE,
    NOTION_DATA_SOFT_FILE,
    NOTION_DATA_TEST_FILE,
    SCIM_SCRIPT,
    PROD_CONFIG_SCRIPT,
    SOFT_CONFIG_SCRIPT,
    TEST_CONFIG_SCRIPT,
    BASE_URL,
    BEARER_TOKEN,
)


def run_script(command):
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        return False

def post_intranet_data(csv_file):
    run_script([
        "python3",
        str(SCIM_SCRIPT),
        "--csv-path", str(csv_file),
        "--base-url", BASE_URL,
        "--bearer-token", BEARER_TOKEN,
        "--show-progress",
    ])

def main():
    parser = argparse.ArgumentParser(
        description="Push users to the Intranet SCIM endpoint."
    )

    parser.add_argument(
        "-s",
        "--soft",
        action="store_true",
        help="Enable soft launch. Push only Corporate employees.",
    )

    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="Enable test launch. Push only Natalie Baldwin.",
    )

    args = parser.parse_args()

    csv_file = NOTION_DATA_FILE # Defaults to full file, assigned to filtered file below

    # Configure for soft launch
    if args.soft:
        if not run_script([
            "python3",
            str(SOFT_CONFIG_SCRIPT),
        ]):
            return

        csv_file = NOTION_DATA_SOFT_FILE
    # Also check for test launch
    elif args.test:
        if not run_script([
            "python3",
            str(TEST_CONFIG_SCRIPT),
        ]):
            return

        csv_file = NOTION_DATA_TEST_FILE
    # Otherwise, configure for production
    else:
        if not run_script([
            "python3",
            str(PROD_CONFIG_SCRIPT),
        ]):
            return

        csv_file = NOTION_DATA_PROD_FILE

    # Post to Intranet
    post_intranet_data(csv_file)

if __name__ == "__main__":
    main()