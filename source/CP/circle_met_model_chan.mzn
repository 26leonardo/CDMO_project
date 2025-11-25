% This is the channeled version of the 'circle_met_model', which adds an
% alternative representation of the domain (the same as the better_model_chan alternative representation)
% to better encode a constraint
include "globals.mzn";

% requires preprocessed file "preprocessed_data.json"
int: n;
int: weeks = n-1;
int: periods = n div 2;
set of int: TEAMS = 1..n;
array[1..2, 1..periods, 1..weeks] of int: calendar; % preprocessed calendar

% Decision variable: a calendar containing the permutation indexes of each team for each week
array[1..periods, 1..weeks] of var 1..periods: permutation_calendar;


% --- Alternative encoding + more efficient constraint with the alternative encoding
set of int: WEEKS = 1..weeks;
set of int: PERIODS = 1..periods;
array[1..n, 1..weeks] of var PERIODS: team_at_p; % indicates for a given index pair (team, week) to which period it is assigned

constraint % channeling constraint: it sets the condition for which the two domain representations are bound
    forall(p in PERIODS, w in WEEKS)(
        team_at_p[ calendar[1, permutation_calendar[p,w], w], w] = p /\
        team_at_p[ calendar[2, permutation_calendar[p,w], w], w] = p
    );

constraint % encodes the constraint that each team can play at most twice in the same period
    forall(t in TEAMS, p in PERIODS)(
        sum([team_at_p[t,w] == p | w in WEEKS]) <= 2
    );

constraint % lightweight symmetry breaking constraint: the first team has to play in the first period of the first week
    team_at_p[1,1] = 1;

% ---


constraint
    % Each permutation index has to be different
    forall(w in 1..weeks)(
        alldifferent([permutation_calendar[p,w] | p in 1..periods])
    );

solve satisfy;

output [
  "{",
  "\"optimal\":true,",
  "\"obj\":null,",
  "\"sol\":[",
    join(",",
         [ "[" ++ join(",",
                       [ "[" ++ show(calendar[ 1, permutation_calendar[p,w], w]) ++ "," ++ show(calendar[ 2, permutation_calendar[p,w], w]) ++ "]"
                       | w in 1..weeks]) ++ "]"
         | p in 1..periods]),
  "]}"
];