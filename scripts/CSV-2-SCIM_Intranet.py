#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create/update SCIM users from Intranet CSV")
    parser.add_argument("--csv-path", required=True, help="Path to input CSV file")
    parser.add_argument("--base-url", required=True, help="SCIM Users endpoint URL")
    parser.add_argument("--bearer-token", required=True, help="Bearer token for SCIM API")
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=50,
        help="Delay in milliseconds between requests (default: 50)",
    )
    parser.add_argument(
        "--no-delays",
        action="store_true",
        help="Disable delays for maximum speed",
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        help="Show detailed progress",
    )
    return parser.parse_args()


def parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return default


def get_first_value(row: Dict[str, Any], keys: List[str], default: str = "") -> str:
    for key in keys:
        if key in row and row[key] is not None:
            value = str(row[key]).strip()
            if value:
                return value
    return default


def convert_date_to_scim(date_str: str) -> str:
    if not date_str or not date_str.strip():
        return ""

    s = date_str.strip()

    if len(s) >= 19 and s[:4].isdigit() and s[4] == "-" and "T" in s:
        return s if s.endswith("Z") else f"{s}Z"

    exact_formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    for fmt in exact_formats:
        try:
            dt = datetime.strptime(s, fmt)
            if fmt in {"%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"}:
                return dt.strftime("%Y-%m-%dT00:00:00Z")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    try:
        candidate = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        print(f"Warning: Could not parse date '{date_str}', leaving empty")
        return ""


def build_post_payload(r: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ],
        "externalId": r["ExternalId"],
        "userName": r["Username"],
        "active": r["Active"],
        "locale": r["Locale"],
        "title": r["JobTitle"],
        "password": r["Password"],
        "emails": [
            {"primary": True, "type": "work", "value": r["Email"]},
        ],
        "name": {
            "familyName": r["FamilyName"],
            "givenName": r["GivenName"],
        },
        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
            "department": r["Department"],
            "organization": r["Company"],
        },
        "urn:ietf:params:scim:schemas:extension:interactsoftware:2.0:User": {
            "jobStartDate": r["JobStartDate"],
            "loginType": r["AuthenticationType"],
            "location": r["Location"],
            "forcePasswordReset": r["ForcePasswordReset"],
        },
    }

    profile_type = str(r.get("ProfileType", "")).strip()
    if profile_type:
        payload["userType"] = profile_type

    return payload


def build_patch_payload(r: Dict[str, Any]) -> Dict[str, Any]:
    operations = [
        {"op": "Replace", "path": "externalId", "value": r["ExternalId"]},
        {"op": "Replace", "path": "userName", "value": r["Username"]},
        {"op": "Replace", "path": "active", "value": r["Active"]},
        {"op": "Replace", "path": "locale", "value": r["Locale"]},
        {"op": "Replace", "path": "title", "value": r["JobTitle"]},
        {"op": "Replace", "path": 'emails[type eq "work"].value', "value": r["Email"]},
        {"op": "Replace", "path": "name.familyName", "value": r["FamilyName"]},
        {"op": "Replace", "path": "name.givenName", "value": r["GivenName"]},
        {
            "op": "Replace",
            "path": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:department",
            "value": r["Department"],
        },
        {
            "op": "Replace",
            "path": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:organization",
            "value": r["Company"],
        },
        {
            "op": "Replace",
            "path": "urn:ietf:params:scim:schemas:extension:interactsoftware:2.0:User:jobStartDate",
            "value": r["JobStartDate"],
        },
        {
            "op": "Replace",
            "path": "urn:ietf:params:scim:schemas:extension:interactsoftware:2.0:User:loginType",
            "value": r["AuthenticationType"],
        },
        {
            "op": "Replace",
            "path": "urn:ietf:params:scim:schemas:extension:interactsoftware:2.0:User:location",
            "value": r["Location"],
        },
        {
            "op": "Replace",
            "path": "urn:ietf:params:scim:schemas:extension:interactsoftware:2.0:User:forcePasswordReset",
            "value": r["ForcePasswordReset"],
        },
        {"op": "Replace", "path": "userType", "value": r["ProfileType"]},
    ]

    filtered_ops = [
        op
        for op in operations
        if op.get("value") is not None
        and (isinstance(op.get("value"), bool) or str(op.get("value")).strip() != "")
    ]

    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": filtered_ops,
    }


def request_json(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/scim+json",
        "Accept": "application/scim+json, application/json",
    }

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url=url, data=data, method=method.upper(), headers=headers)

    try:
        with urlopen(req) as response:
            body = response.read().decode("utf-8")
            if not body.strip():
                return {}
            return json.loads(body)
    except HTTPError as exc:
        details = ""
        try:
            details = exc.read().decode("utf-8")
        except Exception:
            details = ""
        message = f"HTTP {exc.code} {exc.reason}"
        if details:
            message = f"{message} | {details}"
        raise RuntimeError(message) from exc
    except URLError as exc:
        raise RuntimeError(f"Connection error: {exc.reason}") from exc


def test_user_exists(user_name: str, token: str, base_url: str) -> Tuple[bool, Optional[str]]:
    query = urlencode({"filter": f'userName eq "{user_name}"'})
    search_url = f"{base_url}?{query}"

    try:
        response = request_json("GET", search_url, token)
        resources = response.get("Resources") or []
        if resources:
            return True, resources[0].get("id")
        return False, None
    except Exception as exc:
        print(f"Error checking if user exists: {exc}")
        return False, None


def show_progress(current: int, total: int, start_time: float) -> None:
    elapsed = time.time() - start_time
    rate = (current / elapsed) if elapsed > 0 else 0
    eta = ((total - current) / rate) if rate > 0 else 0
    pct = round((current / total) * 100, 1) if total else 100.0
    print(
        f"Progress: {current}/{total} ({pct}%) | "
        f"Rate: {rate:.1f}/sec | ETA: {eta:.0f}sec"
    )


def main() -> int:
    args = parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"CSV file not found at path: {csv_path}")
        return 1

    delay_ms = 0 if args.no_delays else max(args.delay_ms, 0)

    print("=== Intranet CSV to SCIM User Processing ===")
    print(f"Progress reporting: {args.show_progress}")

    start_time = time.time()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    created_count = 0
    updated_count = 0
    failure_count = 0

    for idx, row in enumerate(rows, start=1):
        user_name = get_first_value(row, ["Username", "Email Address"])

        mapped = {
            "ExternalId": get_first_value(row, ["User ID"]),
            "Username": user_name,
            "Email": get_first_value(row, ["Email Address", "Username"]),
            "Active": parse_bool(get_first_value(row, ["Active"], "true"), default=True),
            "Password": get_first_value(row, ["Password"]),
            "FamilyName": get_first_value(row, ["Last Name"]),
            "GivenName": get_first_value(row, ["First Name"]),
            "AuthenticationType": get_first_value(row, ["Authentication Type"]),
            "ProfileType": get_first_value(row, ["Profile Type"]),
            "ForcePasswordReset": parse_bool(
                get_first_value(row, ["Forced Password Reset"], "false"), default=False
            ),
            "Department": get_first_value(row, ["Department"], "Department - Not Specified"),
            "Location": get_first_value(row, ["Location"], "Location - Not Specified"),
            "Company": get_first_value(row, ["Company"], "Company - Not Specified"),
            "JobTitle": get_first_value(row, ["Title"]),
            "JobStartDate": convert_date_to_scim(get_first_value(row, ["Start Date"])),
            "JobEndDate": convert_date_to_scim(get_first_value(row, ["End Date"])),
            "Locale": "en-US",
        }

        if not mapped["Username"]:
            print("Skipping row with missing Username")
            failure_count += 1
            continue

        if args.show_progress:
            print(f"Checking if user exists: {mapped['Username']}")

        exists, user_id = test_user_exists(mapped["Username"], args.bearer_token, args.base_url)

        try:
            if exists and user_id:
                payload = build_patch_payload(mapped)
                request_json(
                    "PATCH",
                    f"{args.base_url.rstrip('/')}/{user_id}",
                    args.bearer_token,
                    payload,
                )
                updated_count += 1
                if args.show_progress:
                    print(f"Updated: {mapped['Username']}")
            else:
                payload = build_post_payload(mapped)
                request_json("POST", args.base_url, args.bearer_token, payload)
                created_count += 1
                if args.show_progress:
                    print(f"Created: {mapped['Username']}")
        except Exception as exc:
            failure_count += 1
            print(f"Failed for {mapped['Username']}: {exc}")

        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

        if args.show_progress or (idx % 10 == 0):
            show_progress(idx, len(rows), start_time)

    elapsed = time.time() - start_time
    print()
    print("=== Summary ===")
    print(f"Total users processed: {len(rows)}")
    print(f"Successfully created: {created_count}")
    print(f"Successfully updated: {updated_count}")
    print(f"Failed to process: {failure_count}")
    print(f"Elapsed: {elapsed:.2f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
CSV to SCIM user processor for Intranet user exports.

Disclaimer:
This script is not supported by Interact and is provided as a reference-only
utility to assist with user provisioning workflows.

Notes:
*** This variant is based on CSV-2-SCIM.py but maps the following headers:
Username, Email Address, User ID, Last Name, First Name, Active, Password,
Authentication Type, Profile Type, Forced Password Reset, Department,
Location, Company, Title, Start Date, End Date

*** Please obtain your {domain} and {token} values from your Interact instance via 
Control Panel > Profile Sources > Created SCIM Profile Source.  Use these respective
values to populate the --base-url and --bearer-token arguments.

*** update the --csv-path argument to point to your CSV file.  The CSV file must be in
UTF-8 format and have a header row with the above column names.

Run instructions:
1) Basic run:
    python ./CSV-2-SCIM_Intranet.py --csv-path "./Intranet_Users_transposed_Contoso_5Rows.csv" --base-url "https://{domain}/api/v2/scim/v2/Users" --bearer-token "{token}"

2) Show detailed progress:
    python ./CSV-2-SCIM_Intranet.py --csv-path "./Intranet_Users_transposed_Contoso_5Rows.csv" --base-url "https://{domain}/api/v2/scim/v2/Users" --bearer-token "{token}" --show-progress

3) Maximum speed (no delay between requests):
    python ./CSV-2-SCIM_Intranet.py --csv-path "./Intranet_Users_transposed_Contoso_5Rows.csv" --base-url "https://{domain}/api/v2/scim/v2/Users" --bearer-token "{token}" --no-delays

4) Custom delay (milliseconds):
    python ./CSV-2-SCIM_Intranet.py --csv-path "./Intranet_Users_transposed_Contoso_5Rows.csv" --base-url "https://{domain}/api/v2/scim/v2/Users" --bearer-token "{token}" --delay-ms 100
"""

