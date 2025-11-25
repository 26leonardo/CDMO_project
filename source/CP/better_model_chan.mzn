% This is the model that has a good encoding of domain and constraints
% It's the same as the 'better_model.mzn' one, but with a channeled alternative representation
% which makes it more efficient in propagation

include "globals.mzn";

int: n;
int: weeks = n-1;
int: periods = n div 2;

set of int: WEEKS = 1..weeks;
set of int: PERIODS = 1..periods;
set of int: TEAMS = 1..n;

array[1..periods, 1..weeks, 1..2] of var TEAMS: calend; % original decision variable encoding


% --- Alternative encoding + more efficient constraint with the alternative encoding

array[1..n, 1..weeks] of var PERIODS: team_at_p; % indicates for a given index pair (team, week) to which period it is assigned

constraint % channeling constraint: it sets the condition for which the two domain representations are bound
    forall(p in PERIODS, w in WEEKS)(
        team_at_p[calend[p,w,1], w ] = p /\
        team_at_p[calend[p,w,2], w ] = p
    );

constraint % encodes the constraint that each team can play at most twice in the same period
    forall(t in TEAMS, p in PERIODS)(
        sum([team_at_p[t,w] == p | w in WEEKS]) <= 2
    );

constraint % lightweight symmetry breaking constraint: the first team has to play in the first period of the first week
    team_at_p[1, 1] = 1;
  
% ---


% --- the following section is equal to the non-channeled version

constraint % this is both a necessary constraint and a symmetry breaking one: it ensures that a single match is
           % played between two different teams, and it does that requiring that the first one will have index strictly less than the second team
    forall(p in PERIODS, w in WEEKS)(
        calend[p,w,1] < calend[p,w,2]
    );

constraint % assures that a team plays exactly once per week (by just checking that all teams in a week must be different)
    forall(w in WEEKS)(
        alldifferent([calend[p,w,1] | p in PERIODS] ++ [calend[p,w,2] | p in PERIODS])
    );

constraint % constrains the fact that two teams must match only once in the entire tournament (by assigning a computed id that considers both teams)
    alldifferent( [ (calend[p,w,1]*n)+calend[p,w,2] | p in PERIODS, w in WEEKS] );


solve satisfy;

output [
  "{",
  "\"optimal\":true,",
  "\"obj\":null,",
  "\"sol\":[",
    join(",",
         [ "[" ++ join(",",
                       [ "[" ++ show(calend[p,w,1]) ++ "," ++ show(calend[p,w,2]) ++ "]"
                       | w in 1..weeks]) ++ "]"
         | p in 1..periods]),
  "]}"
];