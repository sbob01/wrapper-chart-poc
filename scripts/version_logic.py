#!/usr/bin/env python3
import argparse
import pathlib
import re
import sys

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse(v: str):
    m = SEMVER.match(v.strip())
    if not m:
        raise ValueError(f"Invalid x.y.z version: {v}")
    return tuple(map(int, m.groups()))


def read_chart(path: pathlib.Path):
    text = path.read_text()
    chart_m = re.search(r"^version:\s*([^\s#]+)", text, re.M)
    dep_m = re.search(r"(?ms)^dependencies:\s*\n.*?^\s*-\s+name:\s*apigee-hybrid\s*\n(?:.*?\n)*?^\s+version:\s*([^\s#]+)", text)
    if not chart_m or not dep_m:
        raise RuntimeError("Could not locate wrapper version or apigee-hybrid dependency in Chart.yaml")
    return text, chart_m.group(1), dep_m.group(1)


def bump_wrapper(current_wrapper: str, current_upstream: str, target_upstream: str, mode: str):
    wmaj, wmin, wpatch = parse(current_wrapper)
    cmaj, cmin, cpatch = parse(current_upstream)
    tmaj, tmin, tpatch = parse(target_upstream)

    if (tmaj, tmin, tpatch) <= (cmaj, cmin, cpatch):
        return current_wrapper, "none"

    if mode == "patch-only":
        if (tmaj, tmin) != (cmaj, cmin):
            raise ValueError(f"Patch-only branch {cmaj}.{cmin} cannot move to {target_upstream}")
        return f"{wmaj}.{wmin}.{wpatch + 1}", "patch"

    if tmaj > cmaj:
        return f"{wmaj + 1}.0.0", "major"
    if tmin > cmin:
        return f"{wmaj}.{wmin + 1}.0", "minor"
    return f"{wmaj}.{wmin}.{wpatch + 1}", "patch"


def update_chart(path: pathlib.Path, text: str, old_wrapper: str, old_upstream: str, new_wrapper: str, new_upstream: str):
    text = re.sub(r"^version:\s*" + re.escape(old_wrapper) + r"\s*$", f"version: {new_wrapper}", text, count=1, flags=re.M)
    text = re.sub(r"(?m)^(\s+version:\s*)" + re.escape(old_upstream) + r"\s*$", rf"\g<1>{new_upstream}", text, count=1)
    text = re.sub(r"^appVersion:\s*.*$", f'appVersion: "{new_upstream}"', text, count=1, flags=re.M)
    path.write_text(text)


def output(name: str, value: str):
    out = pathlib.Path(__import__("os").environ.get("GITHUB_OUTPUT", "/dev/stdout"))
    with out.open("a") as f:
        f.write(f"{name}={value}\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chart", default="chart-wrapper/Chart.yaml")
    p.add_argument("--target-upstream", required=True)
    p.add_argument("--mode", choices=["latest", "patch-only"], required=True)
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    path = pathlib.Path(args.chart)
    text, wrapper, upstream = read_chart(path)
    new_wrapper, change = bump_wrapper(wrapper, upstream, args.target_upstream, args.mode)
    changed = change != "none"

    if changed and args.write:
        update_chart(path, text, wrapper, upstream, new_wrapper, args.target_upstream)

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
