from z3 import *

def channeled_model_no_check(N):
    W = N - 1
    P = N // 2

    # Define  variables
    Per = [[Int(f"Per_{t}_{w}") for w in range(W)] for t in range(N)]
    Home = [[Bool(f"Home_{t}_{w}") for w in range(W)] for t in range(N)]
    Opp = [[Int(f"Opp_{t}_{w}") for w in range(W)] for t in range(N)]

    solver = Solver()

    # Domains
    for t in range(N):
        for w in range(W):
            solver.add(And(1 <= Per[t][w], Per[t][w] <= P))
            solver.add(And(1 <= Opp[t][w], Opp[t][w] <= N))
            solver.add(Opp[t][w] != t + 1)

    # Channeling from Opp to Per
    for t in range(N):
        for k in range(N):
            if t == k: continue
            for w in range(W):
                solver.add(Implies(Opp[t][w] == k + 1,
                              And(Per[t][w] == Per[k][w], Opp[k][w] == t + 1)))
                solver.add(Implies(And(Per[t][w] == Per[k][w], Opp[k][w] == t + 1),
                              Opp[t][w] == k + 1))
                solver.add(Implies(Opp[t][w] == k + 1, Xor(Home[t][w], Home[k][w])))

    # Main constraints
    for t in range(N):
        solver.add(Distinct([Opp[t][w] for w in range(W)]))
    
    for w in range(W):
        for p in range(1, P+1):
            solver.add(Sum([If(Per[t][w] == p, 1, 0) for t in range(N)]) == 2)

    for t in range(N):
        for p in range(1, P + 1):
            solver.add(Sum([If(Per[t][w] == p, 1, 0) for w in range(W)]) <= 2)

    return solver, Per, Home, Opp

def symmetry_breaking_constraints(N, solver, Home, Per, Opp):
    W = N - 1
    P = N // 2
    
    # Break global home/away flip
    solver.add(Home[0][0])

    # Break the flip of the opponents
    solver.add(Opp[0][0] == N)
    
    # Fix week 0 layout period
    for p in range(1, P+1):
        a, b = p, N + 1 - p
        solver.add(Per[a-1][0] == p)
        solver.add(Per[b-1][0] == p)
    
    # fix team 1 opponents in decreasing order
    for w in range(W-1):
        solver.add(Opp[0][w] > Opp[0][w+1])

    return solver

# function used for imposing the optimization constraints for both approaches
def smt_obj_manual(N, Home, obj, counts, solver):
    W=N-1
    
    # count the number of home games
    count_home = [Sum([If(Home[t][w], 1, 0) for w in range(W)]) for t in range(N)]
    for t in range(N):
        # implied constraint to make the home games converge faster
        solver.add(count_home[t]<=max(counts))
        solver.add(count_home[t]>=min(counts))
    
    # Upper bound and lower bound are imposed on the objective function
    solver.add(Sum([Abs(2*count_home[t] - W) for t in range(N)]) <obj)
    solver.add(Sum([Abs(2*count_home[t] - W) for t in range(N)]) >=N)

    # return the solver and Home
    return solver, Home

# create the matches for the preprocessing
def circle_method_pairs(n):
    assert n % 2 == 0 and n >= 4
    w, p = n - 1, n // 2
    fixed = 1
    others = list(range(2, n+1))
    schedule = {}
    for wk in range(w):
        arr = [fixed] + others
        pairs = [(arr[i], arr[-1 - i]) for i in range(p)]
        schedule[wk] = pairs 
        others = [others[-1]] + others[:-1]

    return schedule

def preprocess_approach_domains(N):
    assert N % 2 == 0 and N >= 4
    W, P = N - 1, N // 2

    # use the circle method to define the thing
    matches = circle_method_pairs(N) 

    # Variables
    Per  = [[Int(f"Per_{t}_{w}")  for w in range(W)] for t in range(N)]
    Home = [[Bool(f"Home_{t}_{w}") for w in range(W)] for t in range(N)]
    solver = Solver()

    # Domains
    for t in range(N):
        for w in range(W):
            solver.add(And(1 <= Per[t][w], Per[t][w] <= P))
        
    # build opponents from circle method
    opp = [[None]*N for _ in range(W)]
    for w in range(W):
        for (u, v) in matches[w]:
            opp[w][u-1] = v
            opp[w][v-1] = u

    # Two teams playing against each other have the same period and
    # two teams not playing against each other have different periods
    for w in range(W):
        for t in range(N):
            o = opp[w][t] - 1 
            solver.add(Per[t][w] == Per[o][w])
            for u in range(N):
                if u != t and u != o:
                    solver.add(Per[t][w] != Per[u][w]) 

    # Implied constraint taken from the other model
    for w in range(W):
        for p in range(1,P+1):
            solver.add(Sum([If(Per[t][w] == p, 1, 0) for t in range(N)]) == 2)

    # Max 2 games in each period for each team
    for t in range(N):
        for p in range(1, P+1):                
            solver.add(Sum([If(Per[t][w] == p, 1, 0) for w in range(W)]) <= 2)

    # One of the two teams is home or away 
    for w in range(W):
        for (u,v) in matches[w]:
            solver.add(Xor(Home[u-1][w], Home[v-1][w])) 

    return solver, Home, Per, matches


def symmetry_breaking_constraints_preprocess(N, solver, Home, Per, matches):
    
    # Break global home/away flip
    solver.add(Home[0][0])
    
    # Fix week 0 layout period
    for i, (u, v) in enumerate(matches[0], start=1):
        solver.add(Per[u-1][0] == i)
        solver.add(Per[v-1][0] == i)
    

    return solver