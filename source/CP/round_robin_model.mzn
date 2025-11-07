include "globals.mzn";

% --- Parameters: requires preprocessed file "preprocessed_data.json"
int: n;
int: weeks = n-1;
int: periods = n div 2;
set of int: TEAMS = 1..n;
array[1..2, 1..periods, 1..weeks] of int: calendar; 

% --- Decision Variables
array[1..periods, 1..weeks] of var 1..periods: permutation_calendar;


constraint
    
     % Each team plays at most twice in the same period over the tournament
    forall(t in TEAMS, p in 1..periods)(
        sum([ calendar[ 1, permutation_calendar[p,w], w] == t \/ calendar[ 2, permutation_calendar[p,w], w] == t | w in 1..weeks ]) <= 2
    )
    /\
    % Each permutation index has to be different
    forall(w in 1..weeks)(
        alldifferent([permutation_calendar[p,w] | p in 1..periods])
    )
;


output [
  "{",
  "\"optimal\":true,",
  "\"obj\":\"None\",",
  "\"sol\":[",
    join(",",
         [ "[" ++ join(",",
                       [ "[" ++ show(calendar[ 1, permutation_calendar[p,w], w]) ++ "," ++ show(calendar[ 2, permutation_calendar[p,w], w]) ++ "]"
                       | w in 1..weeks]) ++ "]"
         | p in 1..periods]),
  "]}"
];