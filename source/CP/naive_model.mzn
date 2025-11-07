include "globals.mzn";
array[int] of tuple(int,int): matches; % dummy, just for compatibility with preprocessing tool


% --- Parameters
int: n; % number of teams (must be even)
set of int: TEAMS = 1..n;
int: weeks = n-1;
int: periods = n div 2;

% --- Decision variables 
% home_team[p,w], away_team[p,w] are the two teams playing in period p, week w
array[1..periods, 1..weeks] of var TEAMS: home_team;
array[1..periods, 1..weeks] of var TEAMS: away_team;

% --- Constraints
constraint
    % 1. Each match is between two different teams
    forall(p in 1..periods, w in 1..weeks) (
        home_team[p,w] != away_team[p,w]
    )
    /\
    % 2. Each team plays once per week
    forall(w in 1..weeks) (
        alldifferent([home_team[p,w] | p in 1..periods] ++
                     [away_team[p,w] | p in 1..periods])
    )
    /\
    % 3. Every pair of teams meets exactly once
    forall(i in TEAMS, j in TEAMS where i < j) (
        sum([ (home_team[p,w] == i /\ away_team[p,w] == j) \/
              (home_team[p,w] == j /\ away_team[p,w] == i)
              | p in 1..periods, w in 1..weeks ]) = 1
    )
    /\
    % 4. Each team plays at most twice in the same period over the tournament
    forall(t in TEAMS, p in 1..periods) (
        sum([ home_team[p,w] == t \/ away_team[p,w] == t | w in 1..weeks ]) <= 2
    );

% --- Solve 
solve satisfy;

% --- Output 
output [
  "{",
  "\"optimal\":true,",
  "\"obj\":\"None\",",
  "\"sol\":[",
    join(",",
         [ "[" ++ join(",",
                       [ "[" ++ show(home_team[p,w]) ++ "," ++ show(away_team[p,w]) ++ "]"
                       | w in 1..weeks]) ++ "]"
         | p in 1..periods]),
  "]}"
];