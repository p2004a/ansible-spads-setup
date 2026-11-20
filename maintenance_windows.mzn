% Picks the maintenance windows of each host, see maintenance_windows in
% group_vars/all.yaml. Refresh the load data with maintenance_windows_load.py,
% then solve and copy the output to host_vars:
%
%   minizinc --solver chuffed maintenance_windows.mzn maintenance_windows.dzn \
%     maintenance_windows_load.dzn -D "$(./maintenance_windows_hosts.py)"
include "cumulative.mzn";

enum REGION;
array[REGION, 0..23] of int: load;         % weekday load per UTC hour, % of peak
array[REGION] of int: max_down;            % max instances in maintenance at once
int: max_down_total;                       % same, over all regions
array[REGION] of set of int: utc_offsets;  % of the region's local time zones

enum HOST;
array[HOST] of REGION: region;
array[HOST] of int: capacity;              % spads_maxInstances

int: overlap_weight;                       % cost of overlap vs. affected players

int: res = 4;  % hours reserved per window: up to 2h drain, shutdown, boot, slack
int: dur = 3;  % hours of load counted as the window's cost

% Each host has 2 windows at the same hour, on Mon and Thu, or Tue and Fri.
% `start` is the first one, in hours from Monday 00:00 UTC.
array[HOST] of var 0..47: start;
function array[int] of var int: windows(HOST: h) = [start[h], start[h] + 72];

% Windows don't touch weekends, which have peak traffic, in UTC nor in the
% region's local time.
function bool: on_weekdays(REGION: r, int: s) =
  forall(t in s..s + res - 1, o in {0} union utc_offsets[r])((t + o + 168) div 24 mod 7 < 5);
constraint forall(h in HOST)
  (start[h] in {s | s in 0..47 where on_weekdays(region[h], s) /\ on_weekdays(region[h], s + 72)});

% Instances in maintenance at once never exceed the limit.
predicate down_at_most(set of HOST: hosts, int: limit) =
  cumulative([w | h in hosts, w in windows(h)], [res | h in hosts, _ in 1..2],
             [capacity[h] | h in hosts, _ in 1..2], limit);
constraint forall(r in REGION)(down_at_most({h | h in HOST where region[h] = r}, max_down[r]));
constraint down_at_most(HOST, max_down_total);

% Hosts of a region with the same capacity are interchangeable, order them.
constraint forall(a, b in HOST where a < b /\ region[a] = region[b] /\ capacity[a] = capacity[b])
  (start[a] < start[b]);

% Players affected: instances in maintenance times the load at that time.
array[REGION, 0..23] of int: cost =
  array2d(REGION, 0..23, [sum(t in s..s + dur - 1)(load[r, t mod 24]) | r in REGION, s in 0..23]);
var int: affected = sum(h in HOST)(capacity[h] * cost[region[h], start[h] mod 24]);

% Instances in maintenance together in a region, times the hours they overlap.
var int: together = sum(a, b in HOST where a < b /\ region[a] = region[b])
  (capacity[a] * capacity[b] * max(0, res - abs(start[a] - start[b])));

solve minimize 100 * affected + overlap_weight * together;

function string: spec(int: s) = ["Mon,Thu", "Tue,Fri"][s div 24 + 1] ++ " "
  ++ (if s mod 24 < 10 then "0" else "" endif) ++ show(s mod 24) ++ ":00 UTC";
output ["# host_vars/\(h)/vars.yaml\nmaintenance_windows: [\"" ++ spec(fix(start[h])) ++ "\"]\n" | h in HOST];
