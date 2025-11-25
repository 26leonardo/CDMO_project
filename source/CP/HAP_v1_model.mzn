% This HAP (Home Away Problem) model is the second part of the pipeline. It is used
% to balance the home matches with the away matches for each team.
% It does it minimizing an objective function, which in this 'v1' version is naive
include "globals.mzn";

% requires partial solution "partial_output.dzn", which contains the results of the unbalanced calendar
int: n;
set of int: TEAMS = 1..n;
int: weeks = n-1;
int: periods = n div 2;
array[1..periods, 1..weeks, 1..2] of int: sol; % matches calendar fixed


% home team index: 1 or 2 for each match
array[1..periods, 1..weeks] of var 1..2: home_team_index;

% Helper: count of home games per team
array[TEAMS] of var 0..weeks: difference;


% Objective function: minimize the maximum difference between the home count and away count of each team
var int: objective_function = max([difference[t] | t in TEAMS]);

constraint % symmetry breaking constraint: indicates that in the first match, the first team has to play at home
    home_team_index[1,1] == 1;

constraint % this is used to assign to the variables the difference between the count of home and away games for each team
    forall(t in TEAMS) (
        difference[t] = abs(( 2*sum([ sol[p,w,home_team_index[p,w]] == t | p in 1..periods, w in 1..weeks ]) ) - weeks)
    );

constraint % indicates that the obj func should be minimized until it reaches the value 'n'
    objective_function >= 1;



solve minimize objective_function;


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