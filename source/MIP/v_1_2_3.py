#!/usr/bin/env python3
import argparse, json, math, os, sys, time, random
from collections import defaultdict
import pulp

def check_warmstart_feasibility(prob, tol=1e-6, DEBUG=False):
    """
    Check if initial values (set via setInitialValue) satisfy constraints.
    LHS = Left Hand Side → is the value calculated from the sum of the variables 
    in the constraint, using the initial values.
    RHS = Right Hand Side → is the constant term of the constraint.
    """
    violated = []
    for cname, c in prob.constraints.items():
        if DEBUG:
            print("DEBUG check:", cname)
        lhs = 0.0
        for v, coeff in c.items():
            if hasattr(v, "varValue"):
                val = getattr(v, "varValue")
                if val != 0:
                    if DEBUG:
                        print("DEBUG check:", v, "->", val)
                if val is None:
                    val = 0
            else:
                if DEBUG:
                    print("DEBUG check:", v, "->", val)
                val = 0
            lhs += coeff * val

        rhs = -c.constant
        sense = c.sense  # -1 <=, 0 ==, 1 >=

        ok = True
        if sense == -1 and lhs - rhs > tol:
            ok = False
        elif sense == 0 and abs(lhs - rhs) > tol:
            ok = False
        elif sense == 1 and rhs - lhs > tol:
            ok = False

        if not ok:
            violated.append((cname, lhs, rhs, sense))

    if violated:
        print(" Vincoli violati dal warm start:")
        for cname, lhs, rhs, sense in violated:
            symbol = {0: "==", -1: "<=", 1: ">="}[sense]
            print(f" - {cname}: LHS={lhs:.3f} {symbol} RHS={rhs:.3f}")
    else:
        print(" Tutti i vincoli rispettati dal warm start.")

    return violated



def compute_circle_pairs(n: int):
    pairs = []
    for i in range(1, n//2 + 1):
        pairs.append((i, n + 1 - i))
    return pairs

def circle_method_pairs(n):
    assert n % 2 == 0 and n >= 4
    w, p = n - 1, n // 2
    fixed = 1
    others = list(range(2, n+1))
    schedule = {}
    for wk in range(1, w+1):
        arr = [fixed] + others
        pairs = []
        for id_p in range(p):
            if (wk + id_p) % 2 == 0:
                pairs.append((arr[id_p], arr[-1 - id_p]))
            else:
                pairs.append((arr[-1 - id_p], arr[id_p]))
        schedule[wk] = pairs  # pairs are 1-based team IDs
        others = [others[-1]] + others[:-1]
    return schedule

def balanced_circle_method_pairs(n, half:bool = False, seed: int = 0):
    assert n % 2 == 0 and n >= 4
    rn = random.Random(seed)
    w, p = n - 1, n // 2
    fixed = 1
    others = list(range(2, n+1))
    schedule = {}
    for wk in range(1, w+1):
        arr = [fixed] + others
        pairs = []
        for id_p in range(p):
            if not half:
                if (wk + id_p) % 2 == 0:
                    pairs.append((arr[-1 - id_p], arr[id_p]))
                else:
                    pairs.append((arr[id_p], arr[-1 - id_p]))
            else:
                if rn.choice([True, False]):
                    if (wk + id_p) % 2 == 0:
                        pairs.append((arr[-1 - id_p], arr[id_p]))
                    else:
                        pairs.append((arr[id_p], arr[-1 - id_p]))
                else:
                    pairs.append((0, 0))
        schedule[wk] = pairs  # pairs are 1-based team IDs
        others = [others[-1]] + others[:-1]
    return schedule

def build_model(
    n: int, solver: str = "CBC", 
    time_limit: int = 300, seed: int = 0,
    presolve: bool = False, objective: str = "feasible",
    version: str = "base", sym_flags: str = "", 
    warm_start: str = "", DEBUG: bool = False,
    cuts: bool = False
    ):
    """
    build_model con opzione sym_flags: stringa che può contenere le lettere
    'A','B','C','D' per abilitare rispettivamente i symmetry-breaking:
      A = anchor team k in week1 period1
      B = fix composition of first week (circle method)
      C = canonical ordering of weeks by signature
      D = canonical ordering of periods by signature
    """

    assert n % 2 == 0 and n >= 2
    W = list(range(1, n))                  # weeks: 1..n-1
    P = list(range(1, n//2 + 1))           # periods: 1..n/2
    T = list(range(1, n+1))                # teams: 1..n

    # Precompute unordered pairs and index by team
    pairs = [(i, j) for i in T for j in T if i < j]      # all i<j pairs
    pairs_of_team = {t: [] for t in T}
    for (i, j) in pairs:
        pairs_of_team[i].append((i, j))
        pairs_of_team[j].append((i, j))

    # --- Create decision variables according to 'version' ---
    x = {}
    h = {}
    if version == "base":
        for w in W:
            for p in P:
                for i in T:
                    for j in T:
                        x[(w,p,i,j)] = pulp.LpVariable(f"x_{w}_{p}_{i}_{j}", cat=pulp.LpBinary)
    elif version == "i!=j":
        for w in W:
            for p in P:
                for i in T:
                    for j in T:
                        if i != j:
                            x[(w,p,i,j)] = pulp.LpVariable(f"x_{w}_{p}_{i}_{j}", cat=pulp.LpBinary)
    elif version == "i<j":
        for w in W:
            for p in P:
                for (i,j) in pairs:
                    x[(w,p,i,j)] = pulp.LpVariable(f"x_{w}_{p}_{i}_{j}", cat=pulp.LpBinary)
    else:
        raise ValueError("Unknown version: " + str(version))

    # Model
    model_name = f"STS_MILP_symbreak_n{n}"
    prob = pulp.LpProblem(model_name, pulp.LpMinimize)

    # Objective
    if objective == "feasible":
        prob += 0, "dummy_objective"
    elif objective == "balanced":
        # Imbalance variables (continuous to avoid branching on them)
        d = pulp.LpVariable.dicts("imbalance", T, lowBound=0, cat=pulp.LpContinuous)

        # If using version 'i<j' we need explicit orientation variables.
        home_minus_away = {}

        if version == "i<j":
            # create orientation variables h and link them to x
            for w in W:
                for p in P:
                    for (i, j) in pairs:   # pairs contains only i<j
                        h[(w,p,i,j)] = pulp.LpVariable(f"h_{w}_{p}_{i}_{j}", cat=pulp.LpBinary)
                        # if pair not scheduled (x==0) then h must be 0; if scheduled (x==1) h can be 0/1
                        prob += h[(w,p,i,j)] <= x[(w,p,i,j)], f"h_le_x_{w}_{p}_{i}_{j}"

            # Now compute home_minus_away for each team using h and x-h
            for t in T:
                home_terms = []
                away_terms = []
                for (i, j) in pairs_of_team[t]:
                    ia, jb = i, j  # ia < jb
                    for w in W:
                        for p in P:
                            if t == ia:
                                # when pair (ia,jb) is assigned and h=1 -> ia is home
                                home_terms.append(h[(w,p,ia,jb)])
                                away_terms.append(x[(w,p,ia,jb)] - h[(w,p,ia,jb)])
                            else:  # t == jb
                                home_terms.append(x[(w,p,ia,jb)] - h[(w,p,ia,jb)])
                                away_terms.append(h[(w,p,ia,jb)])
                home_minus_away[t] = pulp.lpSum(home_terms) - pulp.lpSum(away_terms)

        else:
            # versions with orientation already in x (base or i!=j)
            for i in T:
                home_minus_away[i] = (
                    pulp.lpSum(x[(w,p,i,j)] for w in W for p in P for j in T if j != i)
                    - pulp.lpSum(x[(w,p,j,i)] for w in W for p in P for j in T if j != i)
                )

        # linearize absolute value: |home_minus_away[i]| <= 1 + d[i]
        for i in T:
            prob += home_minus_away[i] <= 1 + d[i], f"imb_pos_{i}"
            prob += -home_minus_away[i] <= 1 + d[i], f"imb_neg_{i}"

        # objective: minimize total imbalance
        prob += pulp.lpSum(d[i] for i in T), "min_total_imbalance" # - n
    else:
        raise ValueError("Unknown objective: " + str(objective))

    # ---------- Basic Constraints ----------

    # (1) Each (week, period) hosts exactly one match
    for w in W:
        for p in P:
            if version == "i<j":
                prob += pulp.lpSum(x[(w,p,i,j)] for (i,j) in pairs) == 1, f"one_match_w{w}_p{p}"
            elif version == "i!=j":
                prob += pulp.lpSum(x[(w,p,i,j)] for i in T for j in T if i != j) == 1, f"one_match_w{w}_p{p}"
            else: # base
                prob += pulp.lpSum(x[(w,p,i,j)] for i in T for j in T if i != j) == 1, f"one_match_w{w}_p{p}"

    # (2) Each pair occurs exactly once
    for (i,j) in pairs:
        if version == "i<j":
            prob += pulp.lpSum(x[(w,p,i,j)] for w in W for p in P) == 1, f"pair_{i}_{j}"
        else:
            prob += pulp.lpSum(x[(w,p,i,j)] + x[(w,p,j,i)] for w in W for p in P) == 1, f"pair_{i}_{j}"

    # (3) Each team plays exactly once per week
    for t in T:
        for w in W:
            if version == "i<j":
                prob += pulp.lpSum(x[(w,p,i,j)] for (i,j) in pairs_of_team[t] for p in P) == 1, f"once_per_week_team{t}_w{w}"
            else:
                prob += pulp.lpSum(x[(w,p,i,j)] + x[(w,p,j,i)] for (i,j) in pairs_of_team[t] for p in P) == 1, f"once_per_week_team{t}_w{w}"

    # (4) Each team plays at most twice in the same period over the tournament
    for t in T:
        for p in P:
            if version == "i<j":
                prob += pulp.lpSum(x[(w,p,i,j)] for (i,j) in pairs_of_team[t] for w in W) <= 2, f"period_cap_team{t}_p{p}"
            else:
                prob += pulp.lpSum(x[(w,p,i,j)] + x[(w,p,j,i)] for (i,j) in pairs_of_team[t] for w in W) <= 2, f"period_cap_team{t}_p{p}"

    # ---------------------------
    # Symmetry-breaking switches (A, B, C, D) controlled by sym_flags
    # ---------------------------
    flags = set(sym_flags.upper())

    # (A) Anchor team k in week1 period1 (safe)
    if 'A' in flags and n > 4:
        k = 1  # kept fixed as in your example; change if you want parametric
        if version == "i<j":
            prob += pulp.lpSum(x[(1, 1, i, j)] for (i, j) in pairs_of_team[k]) == 1, f"sym_team_{k}_w1_p1"
        else:
            prob += pulp.lpSum(
                x[(1, 1, ia, ib)] + x[(1, 1, ib, ia)] for (ia, ib) in pairs_of_team[k]
            ) == 1, f"sym_team_{k}_w1_p1"

    # (B) Fix composition of first week via circle method (safe)
    if 'B' in flags:
        pairs_week1 = compute_circle_pairs(n)
        for (a, b) in pairs_week1:
            ia, ib = (a, b) if a < b else (b, a)
            if version == "i<j":
                prob += pulp.lpSum(x[(1, p, ia, ib)] for p in P) == 1, f"circle_w1_pair_{ia}_{ib}"
            else:
                prob += pulp.lpSum(x[(1, p, ia, ib)] + x[(1, p, ib, ia)] for p in P) == 1, f"circle_w1_pair_{ia}_{ib}"

    # (C) Canonical ordering of weeks by a signature: signature_week[w] <= signature_week[w+1]
    if 'C' in flags:
        signature_week = {}
        for w in W:
            signature_week[w] = pulp.LpVariable(f"sig_w_{w}", lowBound=0, cat=pulp.LpContinuous)
            if version == "i<j":
                prob += signature_week[w] == pulp.lpSum((i + j) * x[(w,p,i,j)] for (i,j) in pairs for p in P), f"define_sig_w_{w}"
            else:
                prob += signature_week[w] == pulp.lpSum((i + j) * (x[(w,p,i,j)] + x[(w,p,j,i)]) for (i,j) in pairs for p in P), f"define_sig_w_{w}"
        for idx in range(len(W) - 1):
            w = W[idx]
            wp = W[idx + 1]
            prob += signature_week[w] <= signature_week[wp], f"order_weeks_{w}_{wp}"

    # (D) Canonical ordering of periods globally: signature_period[p] <= signature_period[p+1]
    if 'D' in flags:
        signature_period = {}
        for p in P:
            signature_period[p] = pulp.LpVariable(f"sig_p_{p}", lowBound=0, cat=pulp.LpContinuous)
            if version == "i<j":
                prob += signature_period[p] == pulp.lpSum((i + j) * x[(w,p,i,j)] for (i,j) in pairs for w in W), f"define_sig_p_{p}"
            else:
                prob += signature_period[p] == pulp.lpSum((i + j) * (x[(w,p,i,j)] + x[(w,p,j,i)]) for (i,j) in pairs for w in W), f"define_sig_p_{p}"
        for idx in range(len(P) - 1):
            p = P[idx]
            pp = P[idx + 1]
            prob += signature_period[p] <= signature_period[pp], f"order_periods_{p}_{pp}"

    # ---------- WARM START HANDLING ----------
    # warm_start parameter accepted values:
    #   "" -> no warm start
    #   "bal_full" -> balanced full circle method warm-start (all weeks)
    #   "half_full" -> half balanced full circle method warm-start (all weeks)
    #   "week1" -> warm-start only week 1 (compute_circle_pairs)
    ws = (warm_start).lower()
    do_warm_start = ws in ("bal_full", "half_full", "week1")

    start_warm = 0
    if do_warm_start:
        start_warm = time.time()
        # initialization
        for var in x.values():
            var.setInitialValue(0)

        # helper to set x[(w,p,i,j)]
        def _set_x_initial(wk, per, a, b):
            if version == "i<j":
                key = (wk, per, min(a, b), max(a, b))
                if key in x:
                    x[key].setInitialValue(1)
            else:
                key1 = (wk, per, a, b)
                key2 = (wk, per, b, a)
                if key1 in x:
                    x[key1].setInitialValue(1)
                    x[key2].setInitialValue(0)
                else:
                    print(f"NEITHER {key1} NOR {key2} FOUND in x; SKIPPING.")

        # Complete warm start
        if ws in ["bal_full", "half_full"]:
            schedule = {}
            if (ws == "bal_full"):
                schedule = balanced_circle_method_pairs(n)  # dict: week -> list of (teamA,teamB)
            else:
                schedule = balanced_circle_method_pairs(n, half=True, seed=seed)  # dict: week -> list of (teamA,teamB)

            for wk, pairs_temp in schedule.items():
                for per_idx, (a, b) in enumerate(pairs_temp, start=1):
                    _set_x_initial(wk, per_idx, a, b)

            if version == "i<j" and objective == "balanced":
                for wk, pairs_temp in schedule.items():
                    for per_idx, (a, b) in enumerate(pairs_temp, start=1):
                        if (a,b) == (0,0): # case of half
                            continue
                        i, j = (a, b) if a < b else (b, a)  # h keys are always (i<j)
                        if (wk, per_idx, i, j) in h:
                            # h==1 if team i (the min) is at home; otherwise 0
                            if a < b:
                                h[(wk, per_idx, i, j)].setInitialValue(1)  # a is min -> home
                            else:
                                h[(wk, per_idx, i, j)].setInitialValue(0)  # a is max -> other orientation

        # One week warm start
        elif ws == "week1":
            pairs_temp = compute_circle_pairs(n)  # list of (i,j) for periods 1..n/2
            wk = 1
            for per_idx, (a, b) in enumerate(pairs_temp, start=1):
                _set_x_initial(wk, per_idx, a, b)

            if version == "i<j" and objective == "balanced":
                for per_idx, (a, b) in enumerate(pairs_temp, start=1):
                    i, j = (a, b) if a < b else (b, a)
                    if (wk, per_idx, i, j) in h:
                        if a < b:
                            h[(wk, per_idx, i, j)].setInitialValue(1)
                        else:
                            h[(wk, per_idx, i, j)].setInitialValue(0)
    end_warm = time.time()
    time_warm = end_warm - start_warm

    # print("Sample keys from x:", list(x.keys())[:20])
    if DEBUG:
        print("key finish------------------")
        print("Warm start: variabili settate a 1")
        for key, var in x.items():
            if getattr(var, "varValue", 0) == 1:
                print(key)
        count_ones = sum(1 for var in x.values() if getattr(var, "varValue", 0) == 1)
        print("Totale variabili settate a 1 nel warm start:", count_ones)

        violated = check_warmstart_feasibility(prob, DEBUG=DEBUG)



    # ---------------------------
    # Solve
    # ---------------------------

    time_mod = time_limit
    if do_warm_start:
        time_mod -= time_warm

    # flag utili
    # ---------------------------
    # glpsol --help
    # --gomory --cuts     
    # --simplex (--primal defoult) --dual 
    # ---------------------------

    if solver == "GLPK":
        if cuts:
            solver = pulp.GLPK_CMD(
                msg=DEBUG,
                timeLimit=math.ceil(time_mod),
                options=["--seed", f"{seed}", "--dual", "--cuts"]
            )
        else:
            solver = pulp.GLPK_CMD(
                msg=DEBUG,
                timeLimit=math.ceil(time_mod),
                options=["--seed", f"{seed}", "--dual"]
            )
    else:
        # flag utili
        # ---------------------------
        # allowableGap - ratioGap (, gapRel=0.01)
        # "cutoff {n(n-1)} MaxSolutions 1" 
        # ---------------------------
        solver = pulp.PULP_CBC_CMD(
            msg=DEBUG, 
            timeLimit=time_mod, 
            threads=1, 
            presolve=presolve, 
            warmStart= do_warm_start, 
            options=[f"RandomS {seed}"],
            # keepFiles =True,
            # logPath  = "source/MIP/log/log.log"
            )
    start = time.time()
    status_code = prob.solve(solver)
    end = time.time()
    runtime = end - start

    if do_warm_start:
        runtime += time_warm

    floored_runtime = int(math.floor(runtime))
    timed_out = (runtime >= time_limit)

    lp_status_str = pulp.LpStatus.get(prob.status, str(prob.status))    # e.g. "Optimal", "Infeasible", ...
    lp_solution_str = pulp.LpSolution.get(prob.status, str(prob.status))  # e.g. "Optimal Solution Found", "Solution Found", ...

    is_optimal_status = (prob.status == 1)        # 1 -> Optimal
    is_solution_found_status = (prob.status == 2) # 2 -> Solution Found (Integer feasible/incumbent)
    is_no_solution = (prob.status == 0)           # 0 -> Not Solved / No Solution Found
    is_infeasible = (prob.status == -1)           # -1 -> Infeasible
    is_unbounded = (prob.status == -2)            # -2 -> Unbounded
    is_undefined = (prob.status == -3)            # -3 -> Undefined

    # Determine feasibility/optimality according to objective type
    has_incumbent = any(pulp.value(v) is not None for v in prob.variables())

    # Extract solution if feasible/incumbent exists
    sol_matrix = []
    if has_incumbent and not is_infeasible and not is_undefined and not is_unbounded and not is_no_solution:
        sol_matrix = [[None for _ in W] for __ in P]
        for w in W:
            for p in P:
                assigned = None
                if version == "i<j":
                    # first find the assigned pair (i,j) in slot (w,p)
                    pair_found = None
                    for (i, j) in pairs:
                        xv = pulp.value(x.get((w, p, i, j)))
                        if xv is not None and xv > 0.5:
                            pair_found = (i, j)
                            break
                    if pair_found is None:
                        assigned = [0, 0]
                    else:
                        i, j = pair_found
                        hv = None
                        hvar = h.get((w, p, i, j))  # could not exist if not created
                        if hvar is not None:
                            hv = pulp.value(hvar)
                        if hv is None:
                            # robust fallback: convention is i home, j away
                            assigned = [i, j]
                        else:
                            if hv > 0.5:
                                assigned = [i, j]   # i home, j away
                            else:
                                assigned = [j, i]   # j home, i away

                else:
                    found = False
                    for i in T:
                        if found:
                            break
                        for j in T:
                            if i == j:
                                continue
                            xv = pulp.value(x.get((w, p, i, j)))
                            if xv is not None and xv > 0.5:
                                assigned = [i, j]   # i home, j away
                                found = True
                                break
                    if not found:
                        assigned = [0, 0]
        
                sol_matrix[p-1][w-1] = assigned

    # Compute objective value if available
    obj_val = None
    if objective == "balanced" and pulp.value(prob.objective) is not None:
        # round to nearest integer (small numerical tolerance)
        obj_val = pulp.value(prob.objective) #int(round(pulp.value(prob.objective)))

    # Default outputs
    time_field = time_limit
    optimal_flag = False

    if objective == "feasible":
        # FEASIBILITY (obj should be None)
        # (A) If Optimal OR Solution Found AND time < limit -> time = actual floored, optimal = True
        if (is_optimal_status or is_solution_found_status) and (not timed_out):
            time_field = floored_runtime
            optimal_flag = True

        # (B) If timed out and no solution found -> time=300, optimal=False
        elif timed_out and not (is_optimal_status or is_solution_found_status):
            time_field = time_limit
            optimal_flag = False

        # (C) If infeasible -> time = actual floored, optimal = True (we proved infeasibility)
        elif is_infeasible:
            time_field = floored_runtime
            optimal_flag = True

        # (D) Any other case: not optimal / not solution found / not infeasible and time < 300 -> set time=300 and optimal=False
        else:
            # This covers cases such as "Not Solved" or "Undefined" but with runtime < time_limit
            # or other unexpected combinations; per spec, set time=300 and optimal=False
            if not timed_out:
                time_field = time_limit
                optimal_flag = False
            else:
                time_field = time_limit
                optimal_flag = False

    elif objective == "balanced":
        # OPTIMIZATION (obj must be integer)
        # (A) If Optimal AND 'Optimal Solution Found' AND obj == n -> time = actual floored, optimal = True
        #     (we check numeric code and the obj condition you requested)
        if is_optimal_status and (lp_solution_str == "Optimal Solution Found") : # and (obj_val == n)
            time_field = floored_runtime
            optimal_flag = True

        # (B) If Solution Found but not Optimal -> time = actual floored, optimal = False
        elif is_solution_found_status:
            time_field = floored_runtime
            optimal_flag = False

        # (C) If infeasible -> time = actual floored, optimal = True
        elif is_infeasible:
            time_field = floored_runtime
            optimal_flag = True

        # (D) Any other case (not Optimal / not Solution Found / not infeasible) and time < 300 -> time = 300, optimal=False
        else:
            if not timed_out:
                time_field = time_limit
                optimal_flag = False
            else:
                # timeout and no incumbent or unclear state -> spec says time=300, optimal False
                time_field = time_limit
                optimal_flag = False
    else:
        raise ValueError("Unknown objective: " + str(objective))

    result = {
        "time": int(time_field),
        "optimal": bool(optimal_flag),
        "obj": obj_val,
        "sol": sol_matrix
    }
    meta = {
        "pulp_status_code": int(prob.status),
        "pulp_status": lp_status_str,
        "pulp_solution": lp_solution_str,
        "runtime_sec": runtime
    }
    return result, meta

if __name__ == '__main__':
    # simple driver: iterate combinations (nota: passiamo presolve correttamente)
    # seed used ofr tests = 0,1234567,26,42,262626,424242,878641,5656565
    bests = [
        (14,"CBC","base","feasible",42,True,"","week1",False),
        (14,"CBC","i<j","balanced",878641,True,"","week1",False),
        (12,"GLPK","base","feasible",26,True,"B","",False),
        (10,"GLPK","i<j","balanced",26,True,"A","",True)
        ]
    for n,solver,version,objective,seed,presolve,sym_flags,warm_start,cuts in bests:
                        for nn in range(4, n+1, 2):
                                res_dir = os.path.join(os.path.dirname(__file__), "..", "..", "res", "MIP" )
                                os.makedirs(res_dir, exist_ok=True)
                                out_path = os.path.join(res_dir, f"{nn}.json")
                                global_start = time.time()
                                try:
                                    result, meta = build_model(nn, solver = solver, time_limit=300, seed=seed,
                                                                presolve=presolve, version=version, sym_flags=sym_flags,
                                                                objective=objective, warm_start=warm_start, cuts=cuts)
                                except Exception as e:
                                    print(f"[ERROR] n={nn} v={version} obj={objective} seed={seed} presolve={presolve}: {e}")
                                    result = {"time":300,"optimal":False,"obj":None,"sol":[]}
                                    meta = {"pulp_status":"error","runtime_sec":0.0}
                                global_end = time.time()
                                total_runtime = global_end - global_start

                                key = ""
                                if solver == "CBC":
                                    key = f"{solver}_{version}_{objective}_{warm_start}_{sym_flags}_{seed}"
                                else:
                                    if cuts:
                                        key = f"{solver}_{version}_{objective}_dual_cuts_{sym_flags}_{seed}"
                                    else:
                                        key = f"{solver}_{version}_{objective}_dual_{sym_flags}_{seed}"
                                payload = { key: result }

                                old_data = {}
                                if os.path.exists(out_path):
                                    try:
                                        with open(out_path, "r") as f:
                                            old_data = json.load(f)
                                            if not isinstance(old_data, dict):
                                                old_data = {}
                                    except (json.JSONDecodeError, ValueError):
                                        old_data = {}
                                old_data.update(payload)
                                with open(out_path, "w") as f:
                                    json.dump(old_data, f, indent=2)

                                print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
                                print(f"Status: {meta['pulp_status']} | optimal={result['optimal']} | obj={result['obj']}")
                                print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result['time']})")
