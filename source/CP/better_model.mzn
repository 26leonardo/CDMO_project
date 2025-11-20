% This is a model that has a better encoding than the 'naive_model', and it exploits
% some symmetry breaking constraints to achieve better results
include "globals.mzn";

int: n;
int: weeks = n-1;
int: periods = n div 2;

set of int: WEEKS = 1..weeks;
set of int: PERIODS = 1..periods;
set of int: TEAMS = 1..n;

array[1..periods, 1..weeks, 1..2] of var TEAMS: calend; % single tridimensional array to represent the calendar


constraint % this is both a necessary constraint and a symmetry breaking one: it ensures that a single match is
           % played between two different teams, and it does that requiring that the first one will have index strictly less than the second team
    forall(p in PERIODS, w in WEEKS)(
        calend[p,w,1] < calend[p,w,2]
    );

constraint % assures that a team plays exactly once per week (by just checking that all teams in a week must be different)
    forall(w in WEEKS)(
        alldifferent([calend[p,w,1] | p in PERIODS] ++ [calend[p,w,2] | p in PERIODS])
    );

constraint % encodes the constraint that each team can play at most twice in the same period
    forall(t in TEAMS, p in PERIODS)(
        sum([calend[p,w,1] == t \/ calend[p,w,2] == t | w in WEEKS]) <= 2
    );

constraint % constrains the fact that two teams must match only once in the entire tournament (by assigning a computed id that considers both teams)
    alldifferent( [ (calend[p,w,1]*n)+calend[p,w,2] | p in PERIODS, w in WEEKS] );

solve satisfy;

% trying various search annotations and heuristics, i've found the default one to be (empirically) the best
%solve :: int_search(calend, first_fail, indomain_min, complete) satisfy;

output [
  "{",
  "\"optimal\":true,",
  "\"obj\":\"None\",",
  "\"sol\":[",
    join(",",
         [ "[" ++ join(",",
                       [ "[" ++ show(calend[p,w,1]) ++ "," ++ show(calend[p,w,2]) ++ "]"
                       | w in 1..weeks]) ++ "]"
         | p in 1..periods]),
  "]}"
];