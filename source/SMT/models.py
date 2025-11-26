# from z3 import *
from pysmt.shortcuts import *
from pysmt.typing import *

def channeled_model_no_check(N):
    W = N - 1
    P = N // 2

    # Define  variables
    Per = [[Symbol(f"Per_{t}_{w}", INT) for w in range(W)] for t in range(N)]
    Home = [[Symbol(f"Home_{t}_{w}", BOOL) for w in range(W)] for t in range(N)]
    Opp = [[Symbol(f"Opp_{t}_{w}", INT) for w in range(W)] for t in range(N)]

    constraints=[]


    for t in range(N):
        for w in range(W):
            constraints.append(And(
                LE(Int(1), Per[t][w]), LE(Per[t][w], Int(P)),
                LE(Int(1), Opp[t][w]), LE(Opp[t][w], Int(N)),
                NotEquals(Opp[t][w], Int(t + 1))
            ))

    # Channeling from Opp to Per
    for t in range(N):
        for k in range(N):
            if t == k: continue
            for w in range(W):
                constraints.append(
                    And(
                Implies(Equals(Opp[t][w], Int(k + 1)), And(Equals(Per[t][w], Per[k][w]), Equals(Opp[k][w], Int(t + 1)))),
                Implies(And(Equals(Per[t][w], Per[k][w]), Equals(Opp[k][w], Int(t + 1))), Equals(Opp[t][w], Int(k + 1))),
                Implies(Equals(Opp[t][w], Int(k + 1)), Xor(Home[t][w], Home[k][w]))
                )
                )


    # Main constraints
    for t in range(N):
        constraints.append(AllDifferent(*[Opp[t][w] for w in range(W)]))
    
    for w in range(W):
        for p in range(1, P+1):
            constraints.append(Equals(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for t in range(N)]), Int(2)))

    for t in range(N):
        for p in range(1, P + 1):
            constraints.append(LE(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for w in range(W)]),Int(2)))


    # Break the home away flip
    constraints.append(Home[0][0])
    
    ## Fix week 0 layout period
    for p in range(1, P+1):
        a, b = p, N + 1 - p
        constraints.append(Equals(Per[a-1][0], Int(p)))
        constraints.append(Equals(Per[b-1][0], Int(p)))
    
    # fix team 1 opponents in decreasing order
    for w in range(W-1):
        constraints.append(GT(Opp[0][w], Opp[0][w+1]))

    formula=And(constraints)

    return formula, Per, Home

def channeled_model_no_check_opt(N, counts, obj, maxs=False):
    W = N - 1
    P = N // 2

    # Define  variables
    Per = [[Symbol(f"Per_{t}_{w}", INT) for w in range(W)] for t in range(N)]
    Home = [[Symbol(f"Home_{t}_{w}", BOOL) for w in range(W)] for t in range(N)]
    Opp = [[Symbol(f"Opp_{t}_{w}", INT) for w in range(W)] for t in range(N)]

    constraints=[]


    for t in range(N):
        for w in range(W):
            constraints.append(And(
                LE(Int(1), Per[t][w]), LE(Per[t][w], Int(P)),
                LE(Int(1), Opp[t][w]), LE(Opp[t][w], Int(N)),
                NotEquals(Opp[t][w], Int(t + 1))
            ))

    # Channeling from Opp to Per
    for t in range(N):
        for k in range(N):
            if t == k: continue
            for w in range(W):
                constraints.append(
                    And(
                Implies(Equals(Opp[t][w], Int(k + 1)), And(Equals(Per[t][w], Per[k][w]), Equals(Opp[k][w], Int(t + 1)))),
                Implies(And(Equals(Per[t][w], Per[k][w]), Equals(Opp[k][w], Int(t + 1))), Equals(Opp[t][w], Int(k + 1))),
                Implies(Equals(Opp[t][w], Int(k + 1)), Xor(Home[t][w], Home[k][w]))
                )
                )


    # Main constraints
    for t in range(N):
        constraints.append(AllDifferent(*[Opp[t][w] for w in range(W)]))
    
    for w in range(W):
        for p in range(1, P+1):
            constraints.append(Equals(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for t in range(N)]), Int(2)))

    for t in range(N):
        for p in range(1, P + 1):
            constraints.append(LE(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for w in range(W)]),Int(2)))

    count_home = [Plus([Ite(Home[t][w], Int(1), Int(0)) for w in range(W)]) for t in range(N)]

    if maxs is False:

        for t in range(N):
            # implied constraint to make the home games converge faster
            constraints.append(LE(count_home[t],Int(max(counts))))
            constraints.append(GE(count_home[t],Int(min(counts))))

        # Upper bound and lower bound are imposed on the objective function
        constraints.append(LT(Plus([Ite(GE(Times(Int(2),count_home[t]) - Int(W),Int(0)), Times(Int(2),count_home[t]) - Int(W), Int(W)-Times(Int(2),count_home[t])) for t in range(N)]), Int(obj)))
        constraints.append(GE(Plus([Ite(GE(Times(Int(2),count_home[t]) - Int(W),Int(0)), Times(Int(2),count_home[t]) - Int(W), Int(W)-Times(Int(2),count_home[t])) for t in range(N)]), Int(N)))
    else:
        abs_diff = []
        for t in range(N):
            diff = Times(Int(2),count_home[t]) - Int(W) 
            abs_t = Ite(GE(diff , Int(0)), diff, -diff)
            abs_diff.append(abs_t)

        M = Symbol('M', INT)
        for t in range(N):
            constraints.append(GE(M,abs_diff[t]))

        #Upper bound and lower bound are imposed on the objective function
        constraints.append(LT(M,Int(max(counts))))
        constraints.append(GE(M,Int(1)))

    # Break global home/away flip
    constraints.append(Home[0][0])

    # Fix week 0 layout period
    for p in range(1, P+1):
        a, b = p, N + 1 - p
        constraints.append(Equals(Per[a-1][0], Int(p)))
        constraints.append(Equals(Per[b-1][0], Int(p)))
    
    # fix team 1 opponents in decreasing order
    for w in range(W-1):
        constraints.append(GT(Opp[0][w], Opp[0][w+1]))

    formula=And(constraints)

    return formula, Home, Per

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
    Per  = [[Symbol(f"Per_{t}_{w}", INT)  for w in range(W)] for t in range(N)]
    Home = [[Symbol(f"Home_{t}_{w}", BOOL) for w in range(W)] for t in range(N)]
    constraints = []

    # Domains
    for t in range(N):
        for w in range(W):
            constraints.append(And(LE(Int(1), Per[t][w]), LE(Per[t][w], Int(P))))
        
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
            constraints.append(Equals(Per[t][w],Per[o][w]))
            for u in range(N):
                if u != t and u != o:
                    constraints.append(NotEquals(Per[t][w], Per[u][w]))

    # Implied constraint taken from the other model
    for w in range(W):
        for p in range(1, P+1):
            constraints.append(Equals(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for t in range(N)]), Int(2)))

    # Max 2 games 
    for t in range(N):
        for p in range(1, P + 1):
            constraints.append(LE(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for w in range(W)]),Int(2)))


    # One of the two teams is home or away 
    for w in range(W):
        for (u,v) in matches[w]:
            constraints.append(Xor(Home[u-1][w], Home[v-1][w]))

    # Break global home/away flip
    constraints.append(Home[0][0])
    
    # Fix week 0 layout period
    for i, (u, v) in enumerate(matches[0], start=1):
        constraints.append(Equals(Per[u-1][0], Int(i)))
        constraints.append(Equals(Per[v-1][0], Int(i)))

    formula = And(constraints) 

    return formula, Per, Home

def preprocess_approach_domains_opt(N, counts, obj,maxs=False):
    assert N % 2 == 0 and N >= 4
    W, P = N - 1, N // 2

    # use the circle method to define the thing
    matches = circle_method_pairs(N) 

    # Variables
    Per  = [[Symbol(f"Per_{t}_{w}", INT)  for w in range(W)] for t in range(N)]
    Home = [[Symbol(f"Home_{t}_{w}", BOOL) for w in range(W)] for t in range(N)]
    constraints = []

    # Domains
    for t in range(N):
        for w in range(W):
            constraints.append(And(LE(Int(1), Per[t][w]), LE(Per[t][w], Int(P))))
        
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
            constraints.append(Equals(Per[t][w],Per[o][w]))
            for u in range(N):
                if u != t and u != o:
                    constraints.append(NotEquals(Per[t][w], Per[u][w]))

    # Implied constraint taken from the other model
    for w in range(W):
        for p in range(1, P+1):
            constraints.append(Equals(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for t in range(N)]), Int(2)))

    # Max 2 games 
    for t in range(N):
        for p in range(1, P + 1):
            constraints.append(LE(Plus([Ite(Equals(Per[t][w],Int(p)), Int(1), Int(0)) for w in range(W)]),Int(2)))

    # One of the two teams is home or away 
    for w in range(W):
        for (u,v) in matches[w]:
            constraints.append(Xor(Home[u-1][w], Home[v-1][w]))
#
    count_home = [Plus([Ite(Home[t][w], Int(1), Int(0)) for w in range(W)]) for t in range(N)]
    if maxs is False:
        for t in range(N):
            # implied constraint to make the home games converge faster
            constraints.append(LE(count_home[t],Int(max(counts))))
            constraints.append(GE(count_home[t],Int(min(counts))))

        # Upper bound and lower bound are imposed on the objective function
        diffs = [Times(Int(2), count_home[t]) - Int(W) for t in range(N)]
        abs_terms = [Ite(GE(d, Int(0)), d, -d) for d in diffs]

        sum_abs = Plus(abs_terms)

        constraints.append(LT(sum_abs, Int(obj)))
        constraints.append(GE(sum_abs, Int(N)))
    else:
        abs_diff = []
        for t in range(N):
            diff = Times(Int(2),count_home[t]) - Int(W) 
            abs_t = Ite(GE(diff , Int(0)), diff, -diff)
            abs_diff.append(abs_t)

        for t1, t2 in zip(range(N-1), range(1, N)):
            constraints.append(GE(abs_diff[t1] , abs_diff[t2]))

        #Upper bound and lower bound are imposed on the objective function
        constraints.append(LT(abs_diff[0],Int((max(counts)+1)//2)))
        constraints.append(GE(abs_diff[0],Int(1)))

    # Break global home/away flip
    constraints.append(Home[0][0])
    
    # Fix week 0 layout period
    for i, (u, v) in enumerate(matches[0], start=1):
        constraints.append(Equals(Per[u-1][0], Int(i)))
        constraints.append(Equals(Per[v-1][0], Int(i)))

    formula = And(constraints) 

    return formula, Per, Home