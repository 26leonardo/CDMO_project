include "globals.mzn";

% --- Parameters: requires partial solution "partial_output.dzn"
int: n;
set of int: TEAMS = 1..n;
int: weeks = n-1;
int: periods = n div 2;
array[1..periods, 1..weeks, 1..2] of int: sol; % matches calendar fixed

% --- Decision Variables
% home team index: 1 or 2 for each match
array[1..periods, 1..weeks] of var 1..2: home_team_index;

% --- Helper: count of home games per team
array[TEAMS] of var 0..weeks: home_games;


% --- Objective: minimize imbalance
var int: max_home = max(home_games);
var int: min_home = min(home_games);
var int: objective_function = max_home - min_home;

constraint
    home_team_index[1,1] == 1
    /\
    forall(t in TEAMS) (
        home_games[t] = sum([ sol[p,w,home_team_index[p,w]] == t | p in 1..periods, w in 1..weeks ])
    )
    /\ 
    objective_function >= 1
 ;



solve minimize objective_function;

% --- Output
output [
  "{",
  "\"optimal\":" ++ show(objective_function == 1) ++ ",",
  "\"obj\":" ++ show(objective_function) ++ ",",
  "\"sol\":[",
    join(",",
         [ "[" ++ join(",", 
                       [ "[" ++ show(sol[p,w ,home_team_index[p,w]]) ++ "," ++ show(sol[p,w ,3-home_team_index[p,w]]) ++ "]"
                       | w in 1..weeks]) ++ "]"
         | p in 1..periods]),
  "]}"
];