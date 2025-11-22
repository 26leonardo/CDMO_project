% This model provides a naive baseline on which build up better encodings and techniques
include "globals.mzn";

int: n; 
set of int: TEAMS = 1..n;
int: weeks = n-1;
int: periods = n div 2;


% home_team[p,w], away_team[p,w] are the two teams playing in period p, week w
array[1..periods, 1..weeks] of var TEAMS: home_team;
array[1..periods, 1..weeks] of var TEAMS: away_team;


constraint % Each match is between two different teams
    forall(p in 1..periods, w in 1..weeks) (
        home_team[p,w] != away_team[p,w]
    );

constraint % Each team plays once per week
    forall(w in 1..weeks) (
        alldifferent([home_team[p,w] | p in 1..periods] ++
                     [away_team[p,w] | p in 1..periods])
    );

constraint% Every pair of teams meets exactly once
    forall(i in TEAMS, j in TEAMS where i < j) (
        sum([ (home_team[p,w] == i /\ away_team[p,w] == j) \/
              (home_team[p,w] == j /\ away_team[p,w] == i)
              | p in 1..periods, w in 1..weeks ]) = 1
    );

constraint % Each team plays at most twice in the same period over the tournament
    forall(t in TEAMS, p in 1..periods) (
        sum([ home_team[p,w] == t \/ away_team[p,w] == t | w in 1..weeks ]) <= 2
    );


solve satisfy;


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