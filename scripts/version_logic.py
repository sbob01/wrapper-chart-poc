#!/usr/bin/env python3

import argparse
import os
import pathlib
import re
import sys


APIGEE_DEPENDENCIES = [
    "apigee-operator",
    "apigee-datastore",
    "apigee-telemetry",
    "apigee-redis",
    "apigee-ingress-manager",
    "apigee-org",
    "apigee-env",
    "apigee-virtualhost",
]

REFERENCE_DEPENDENCY = "apigee-operator"

# Wrapper versions follow standard x.y.z semantic versioning.
WRAPPER_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
)

# Apigee versions use x.y.z and may optionally contain a hotfix suffix:
#   1.17.10
#   1.17.10hotfix.1
#   1.17.10hotfix.22
APIGEE_VERSION = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:hotfix\.(0|[1-9]\d*))?$"
)


def parse_wrapper(v: str):
    """Parse wrapper x.y.z version."""
    m = WRAPPER_VERSION.match(v.strip())

    if not m:
        raise ValueError(f"Invalid wrapper x.y.z version: {v}")

    return tuple(map(int, m.groups()))


def parse_apigee(v: str):
    """
    Parse an Apigee version into a comparable tuple.

    Examples:
        1.17.10            -> (1, 17, 10, 0)
        1.17.10hotfix.1   -> (1, 17, 10, 1)
        1.17.10hotfix.22  -> (1, 17, 10, 22)

    This makes normal tuple comparison usable for determining
    whether a newer Apigee release is available.
    """
    m = APIGEE_VERSION.match(v.strip())

    if not m:
        raise ValueError(f"Invalid Apigee version: {v}")

    major, minor, patch, hotfix = m.groups()

    return (
        int(major),
        int(minor),
        int(patch),
        int(hotfix or 0),
    )




def bump_wrapper(
    current_wrapper: str,
    current_upstream: str,
    target_upstream: str,
    mode: str,
):
    # Wrapper follows normal semantic versioning.
    wmaj, wmin, wpatch = parse_wrapper(current_wrapper)

    # Apigee has an additional hotfix component.
    cmaj, cmin, cpatch, chotfix = parse_apigee(current_upstream)
    tmaj, tmin, tpatch, thotfix = parse_apigee(target_upstream)

    current = (cmaj, cmin, cpatch, chotfix)
    target = (tmaj, tmin, tpatch, thotfix)

    # Nothing to do if the discovered upstream version is equal
    # to or older than the version currently used by the wrapper.
    if target <= current:
        return current_wrapper, "none"

    # Maintenance branches release/apigee-X.Y are only allowed
    # to evolve inside their existing major.minor line.
    #
    # Both regular patches and hotfixes are therefore valid:
    #
    #   1.17.10 -> 1.17.11
    #   1.17.10 -> 1.17.10hotfix.22
    #
    # but:
    #
    #   1.17.x -> 1.18.x
    #
    # is rejected.
    if mode == "patch-only":
        if (tmaj, tmin) != (cmaj, cmin):
            raise ValueError(
                f"Patch-only branch {cmaj}.{cmin} "
                f"cannot move to {target_upstream}"
            )

        return f"{wmaj}.{wmin}.{wpatch + 1}", "patch"

    # A new Apigee major creates a new major wrapper version.
    if tmaj > cmaj:
        return f"{wmaj + 1}.0.0", "major"

    # A new Apigee minor creates a new minor wrapper version.
    if tmin > cmin:
        return f"{wmaj}.{wmin + 1}.0", "minor"

    # Both upstream patches and hotfixes produce a wrapper patch.
    return f"{wmaj}.{wmin}.{wpatch + 1}", "patch"


def extract_dependencies(text: str):
    dependencies = {}

    dep_block_match = re.search(
        r"(?ms)^dependencies:\s*\n(?P<body>(?:^\s+-.*(?:\n(?!\S).*)*)+)",
        text,
    )

    if not dep_block_match:
        raise RuntimeError("Could not locate dependencies block in Chart.yaml")

    body = dep_block_match.group("body")

    entries = re.finditer(
        r"(?ms)^\s*-\s+name:\s*(?P<name>[^\s#]+)"
        r"(?P<body>.*?)(?=^\s*-\s+name:|\Z)",
        body,
    )

    for entry in entries:
        name = entry.group("name")
        entry_body = entry.group("body")

        version_match = re.search(
            r"(?m)^\s+version:\s*([^\s#]+)",
            entry_body,
        )

        if version_match:
            dependencies[name] = version_match.group(1)

    return dependencies


def read_chart(path: pathlib.Path):
    text = path.read_text()

    chart_m = re.search(
        r"(?m)^version:\s*([^\s#]+)",
        text,
    )

    if not chart_m:
        raise RuntimeError("Could not locate wrapper version in Chart.yaml")

    dependencies = extract_dependencies(text)

    missing = [
        dep
        for dep in APIGEE_DEPENDENCIES
        if dep not in dependencies
    ]

    if missing:
        raise RuntimeError(
            "Missing expected Apigee dependencies in Chart.yaml: "
            + ", ".join(missing)
        )

    upstream = dependencies[REFERENCE_DEPENDENCY]

    inconsistent = {
        name: version
        for name, version in dependencies.items()
        if name in APIGEE_DEPENDENCIES and version != upstream
    }

    if inconsistent:
        details = ", ".join(
            f"{name}={version}"
            for name, version in inconsistent.items()
        )
        raise RuntimeError(
            f"Apigee dependencies are not aligned with "
            f"{REFERENCE_DEPENDENCY}={upstream}: {details}"
        )

    return text, chart_m.group(1), upstream



def update_dependency_version(
    text: str,
    dependency_name: str,
    new_version: str,
):
    pattern = (
        rf"(?ms)"
        rf"(^\s*-\s+name:\s*{re.escape(dependency_name)}\s*$"
        rf".*?"
        rf"^\s+version:\s*)"
        rf"([^\s#]+)"
    )

    updated_text, count = re.subn(
        pattern,
        rf"\g<1>{new_version}",
        text,
        count=1,
    )

    if count != 1:
        raise RuntimeError(
            f"Could not update dependency {dependency_name}"
        )

    return updated_text


def update_chart(
    path: pathlib.Path,
    text: str,
    old_wrapper: str,
    new_wrapper: str,
    new_upstream: str,
):
    text, count = re.subn(
        r"(?m)^version:\s*" + re.escape(old_wrapper) + r"\s*$",
        f"version: {new_wrapper}",
        text,
        count=1,
    )

    if count != 1:
        raise RuntimeError("Could not update wrapper version")

    for dependency in APIGEE_DEPENDENCIES:
        text = update_dependency_version(
            text,
            dependency,
            new_upstream,
        )

    text = re.sub(
        r'(?m)^appVersion:\s*.*$',
        f'appVersion: "{new_upstream}"',
        text,
        count=1,
    )

    path.write_text(text)


def output(name: str, value: str):
    output_path = os.environ.get("GITHUB_OUTPUT")

    if output_path:
        with pathlib.Path(output_path).open("a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--chart",
        default="chart-wrapper/Chart.yaml",
    )

    parser.add_argument(
        "--target-upstream",
        required=True,
    )

    parser.add_argument(
        "--mode",
        choices=["latest", "patch-only"],
        required=True,
    )

    parser.add_argument(
        "--write",
        action="store_true",
    )

    args = parser.parse_args()

    path = pathlib.Path(args.chart)

    text, wrapper, upstream = read_chart(path)

    new_wrapper, change = bump_wrapper(
        wrapper,
        upstream,
        args.target_upstream,
        args.mode,
    )

    changed = change != "none"

    if changed and args.write:
        update_chart(
            path,
            text,
            wrapper,
            new_wrapper,
            args.target_upstream,
        )

    print(f"Current upstream: {upstream}")
    print(f"Target upstream:  {args.target_upstream}")
    print(f"Current wrapper:  {wrapper}")
    print(f"Target wrapper:   {new_wrapper}")
    print(f"Change type:      {change}")

    output("changed", str(changed).lower())
    output("old_upstream", upstream)
    output("new_upstream", args.target_upstream)
    output("old_wrapper", wrapper)
    output("new_wrapper", new_wrapper)
    output("change_type", change)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
