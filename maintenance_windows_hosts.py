#!/usr/bin/env python3
"""Prints region and capacity of each host from host_vars for maintenance_windows.mzn.

Hosts are named after their region, e.g. eu4 is in EU, matching the region
names in maintenance_windows_load.dzn. Hosts not named like that are skipped.
"""

import pathlib
import re

import yaml

hosts = {}
for path in sorted(pathlib.Path(__file__).parent.glob("host_vars/*/vars.yaml")):
    host = path.parent.name
    if m := re.fullmatch(r"([a-z]+)\d+", host):
        hosts[host] = (m.group(1).upper(), yaml.safe_load(path.read_text())["spads_maxInstances"])

print("HOST = {" + ", ".join(hosts) + "};")
print("region = [" + ", ".join(f"{h}: {r}" for h, (r, _) in hosts.items()) + "];")
print("capacity = [" + ", ".join(f"{h}: {c}" for h, (_, c) in hosts.items()) + "];")
