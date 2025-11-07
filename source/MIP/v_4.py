#!/usr/bin/env python3
"""
Permutation-of-preprocessed-pairs STS model (PuLP + CBC) with warm-start and
balanced objective support (orientation variables h linked to y).

- Precompute pairs via circle method (oriented pairs).
- Decision vars: y[(w,k,per)] = pair k of week w is placed in period per.
- If objective == "balanced": create h[(w,k,per)] binary = 1 if that assignment places
  the first team in the precomputed pair at home in that slot.
  Link: h[(w,k,per)] <= y[(w,k,per)] (so h forced 0 when y=0).
- Balanced objective: minimize sum_t d[t], with -d[t] <= home_minus_away[t] <= d[t].
- Warm start: options "random_full", "random_half", "week1".
- Time limit: solver gets time_limit minus preprocessing+warmstart time.
"""

import random, time, math, os, argparse, json, sys
from typing import Dict, List, Tuple
import pulp
from collections import defaultdict

def balanced_circle_method_pairs(n: int) -> Dict[int, List[Tuple[int,int]]]:
    """Return oriented pairs (home,away) for each week using circle method."""
    assert n % 2 == 0 and n >= 4
    w = n - 1
    p = n // 2
    fixed = 1
    others = list(range(2, n+1))
    schedule = {}
    for wk in range(1, w+1):
        arr = [fixed] + others[:]
        pairs = []
        for id_p in range(p):
            if (wk + id_p) % 2 == 0:
                pairs.append((arr[-1 - id_p], arr[id_p]))
            else:
                pairs.append((arr[id_p], arr[-1 - id_p]))
        schedule[wk] = pairs
        others = [others[-1]] + others[:-1]
    return schedule

def check_warmstart_feasibility_using_initials(prob, tol=1e-6, DEBUG=False):
    """
    Check constraints against variables' _initialValue (set via var.setInitialValue).
    Returns list of violated constraints (name, lhs, rhs, sense).
    """
    violated = []
    for cname, c in prob.constraints.items():
        lhs = 0.0
        for v, coeff in c.items():
            iv = getattr(v, "_initialValue", None)
            if iv is None:
                iv = 0.0
            lhs += coeff * float(iv)
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
    if DEBUG and violated:
        print("Warm-start violates constraints:")
        for (name, lhs, rhs, sense) in violated:
            sym = {0: "==", -1: "<=", 1: ">="}[sense]
            print(f" - {name}: LHS={lhs:.6f} {sym} RHS={rhs:.6f}")
    return violated

def build_model_with_permutations(n: int,
                                  time_limit: int = 300,
                                  seed: int = 0,
                                  presolve: bool = True,
                                  warm_start: str = "",
                                  objective: str = "feasible",
                                  DEBUG: bool = False,
                                  solver: str = "CBC",
                                  cuts: bool = False
                                  ):
    """
    Build and solve. Returns (result, meta).
    result: {time, optimal, obj, sol}
    meta: {runtime_sec, pulp_status, pulp_status_code}
    """
    assert n % 2 == 0 and n >= 4
    start_total = time.time()
    rn = random.Random(seed)

    W = list(range(1, n))          # weeks
    P = list(range(1, n//2 + 1))   # periods
    T = list(range(1, n+1))        # teams
    p = len(P)

    # --- Preprocessing: build oriented pairs per week ---
    t0_pre = time.time()
    pairs_list_by_week = balanced_circle_method_pairs(n)   # oriented (home, away)
    # appearance_map: team -> list of (w,k)
    appearance_map = {t: [] for t in T}
    for w in W:
        for k, (a, b) in enumerate(pairs_list_by_week[w]):
            appearance_map[a].append((w, k))
            appearance_map[b].append((w, k))
    t1_pre = time.time()
    preprocess_time = t1_pre - t0_pre

    # --- Decision vars: y[(w,k,per)] ---
    y = {}
    for w in W:
        for k in range(p):
            for per in P:
                y[(w,k,per)] = pulp.LpVariable(f"y_{w}_{k}_{per}", cat=pulp.LpBinary)

    # If objective==balanced we need orientation variables h[(w,k,per)]
    h = {}  # only created if objective == 'balanced'
    if objective == "balanced":
        for w in W:
            for k in range(p):
                for per in P:
                    # h = 1 means "first element of stored pair (pairs_list_by_week[w][k]) is home"
                    h[(w,k,per)] = pulp.LpVariable(f"h_{w}_{k}_{per}", cat=pulp.LpBinary)

    # --- Build problem ---
    prob = pulp.LpProblem(f"STS_perm_pairs_n{n}", pulp.LpMinimize)

    # Objective: feasibility dummy or balanced objective
    if objective == "feasible":
        prob += 0, "dummy_objective"
    elif objective == "balanced":
        # d[t] continuous >= 0 linearize |home_minus_away[t]|
        d = pulp.LpVariable.dicts("imbalance", T, lowBound=0, cat=pulp.LpContinuous)

    # (A) Assign each pair k in week w to exactly one period
    for w in W:
        for k in range(p):
            prob += pulp.lpSum(y[(w,k,per)] for per in P) == 1, f"assign_once_w{w}_k{k}"

    # (B) Permutation: each period per in week w has exactly one pair
    for w in W:
        for per in P:
            prob += pulp.lpSum(y[(w,k,per)] for k in range(p)) == 1, f"one_pair_per_period_w{w}_per{per}"

    # (C) Global cap: each team t appears in period per at most twice
    for t in T:
        for per in P:
            vars_involved = [ y[(w,k,per)] for (w,k) in appearance_map[t] ]
            if vars_involved:
                prob += pulp.lpSum(vars_involved) <= 2, f"period_cap_team{t}_per{per}"
    # (E) Symmetry breaking: anchor partial week1
    for k in range(p//3):
        if k % 2 == 0:
            prob += y[(1, k, k+1)] == 1, f"fix_week1_identity_k{k}"

    # If balanced: link h and y and define home_minus_away[t]
    if objective == "balanced":
        # linking: h <= y ensures if y=0 then h=0; when y=1 h free {0,1}
        for w in W:
            for k in range(p):
                for per in P:
                    prob += h[(w,k,per)] <= y[(w,k,per)], f"h_le_y_{w}_{k}_{per}"

        # build home_minus_away[t] as expression
        home_minus_away = {}
        for t in T:
            home_terms = []
            away_terms = []
            for (w,k) in appearance_map[t]:
                # pair = pairs_list_by_week[w][k] is (a,b) with a<b or not — we treat 'first' element as index 0
                a,b = pairs_list_by_week[w][k]
                if t == a:
                    # if t is the first element in stored pair: home contribution is h, away is y-h
                    for per in P:
                        home_terms.append(h[(w,k,per)])
                        away_terms.append(y[(w,k,per)] - h[(w,k,per)])
                else:
                    # t == b: home contribution is y-h, away contribution is h
                    for per in P:
                        home_terms.append(y[(w,k,per)] - h[(w,k,per)])
                        away_terms.append(h[(w,k,per)])
            if home_terms:
                home_minus_away[t] = pulp.lpSum(home_terms) - pulp.lpSum(away_terms)
            else:
                home_minus_away[t] = 0

        # linearize absolute value: -d[t] <= home_minus_away[t] <= d[t]
        for t in T:
            prob += home_minus_away[t] <= 1+d[t], f"imb_pos_{t}"
            prob += -home_minus_away[t] <= 1+d[t], f"imb_neg_{t}"

        # objective: minimize total imbalance
        prob += pulp.lpSum(d[t] for t in T), "min_total_imbalance"

    # -------------------------
    # Warm start: set initial values for y (and h if present)
    # -------------------------
    t0_warm = time.time()
    ws = (warm_start or "").lower()
    do_warm = ws in ("random_full", "random_half", "week1")
    if do_warm:
        # Build initial_map: for every (w,k) give a candidate period
        initial_map = {}
        for w in W:
            perm = P[:]
            rn.shuffle(perm)
            for k in range(p):
                initial_map[(w,k)] = perm[k]

        # If 'week1': we only set the first week; use identity mapping (k -> k+1)
        if ws == "week1":
            for k in range(p):
                initial_map[(1,k)] = P[k]  # identity: k->period k (P is 1..p)

        # Decide which slots to set
        slots = list(initial_map.keys())
        if ws == "random_half":
            slots = rn.sample(slots, len(slots)//2)

        # initialize all y to 0 to have consistent MIPStart
        for var in y.values():
            var.setInitialValue(0)

        # set chosen slots to 1 in their assigned period
        for (w,k) in slots:
            assigned_per = initial_map[(w,k)]
            for per in P:
                val = 1 if per == assigned_per else 0
                y[(w,k,per)].setInitialValue(val)
            # if h exists, set h for the chosen (w,k,assigned_per) according to preprocessed orientation:
            if objective == "balanced":
                # precomputed orientation: pairs_list_by_week[w][k] = (a,b) -> first is home
                # so if we want to reflect that, set h = 1 at that chosen (w,k,assigned_per)
                h[(w,k,assigned_per)].setInitialValue(1)
                # set other h in same (w,k,per) to 0 (already default 0 if we didn't set)
                for per in P:
                    if per != assigned_per:
                        h[(w,k,per)].setInitialValue(0)
    t1_warm = time.time()
    warm_time = t1_warm - t0_warm

    # Optional debug check of warm-start feasibility against constraints
    if DEBUG and do_warm:
        violated = check_warmstart_feasibility_using_initials(prob, DEBUG=DEBUG)
        if violated:
            print(f"DEBUG: warm-start violates {len(violated)} constraints (this is OK if warm-start partial).")

    # -------------------------
    # Solve: adjust solver time limit subtracting preprocess+warm time
    # -------------------------
    pre_warm_time = preprocess_time + warm_time
    adjusted_time_limit = max(1.0, time_limit - pre_warm_time)

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
                timeLimit=math.ceil(adjusted_time_limit),
                options=["--seed", f"{seed}", "--dual", "--cuts"]
            )
        else:
            solver = pulp.GLPK_CMD(
                msg=DEBUG,
                timeLimit=math.ceil(adjusted_time_limit),
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
            timeLimit=adjusted_time_limit, 
            threads=1, 
            presolve=presolve, 
            warmStart= do_warm, 
            options=[f"RandomS {seed}"],
            # keepFiles =True,
            # logPath  = "source/MIP/log/log.log"
            )

    t0_solve = time.time()
    status_code = prob.solve(solver)
    t1_solve = time.time()

    total_runtime = time.time() - start_total   # includes preprocess + warm + solve
    solve_runtime = t1_solve - t0_solve

    # Interpret status & extract
    lp_status = pulp.LpStatus.get(prob.status, str(prob.status))
    has_incumbent = any(pulp.value(v) is not None for v in prob.variables())

    is_optimal_status = (prob.status == 1)        # 1 -> Optimal
    is_solution_found_status = (prob.status == 2) # 2 -> Solution Found (Integer feasible/incumbent)
    is_no_solution = (prob.status == 0)           # 0 -> Not Solved / No Solution Found
    is_infeasible = (prob.status == -1)           # -1 -> Infeasible
    is_unbounded = (prob.status == -2)            # -2 -> Unbounded
    is_undefined = (prob.status == -3)            # -3 -> Undefined


    sol_matrix = [[None for _ in W] for __ in P]  # periods x weeks
    if has_incumbent and not is_infeasible and not is_undefined and not is_unbounded and not is_no_solution:
        for w in W:
            for per in P:
                assigned = None
                for k in range(p):
                    val = pulp.value(y[(w,k,per)])
                    if val is not None and val > 0.5:
                        assigned = pairs_list_by_week[w][k]
                        break
                if assigned is None:
                    assigned = [0,0]
                sol_matrix[per-1][w-1] = list(assigned)
    else:
        sol_matrix = []
    # Decide solved_flag & time_field (feasibility semantics)
    floored_total = int(math.floor(total_runtime))
    # simple rule: solved if incumbent found within allowed total time or infeasible proven
    solved_flag = (is_solution_found_status and total_runtime <= time_limit) or (is_optimal_status and total_runtime <= time_limit) or (is_infeasible)
    time_field = floored_total if solved_flag else time_limit

    result = {
        "time": int(time_field),
        "optimal": bool(solved_flag),
        "obj": None if objective == "feasible" else (int(round(pulp.value(prob.objective))) if pulp.value(prob.objective) is not None else None),
        "sol": sol_matrix
    }
    meta = {
        "runtime_sec_total": total_runtime,
        "runtime_sec_solve": solve_runtime,
        "preprocess_time": preprocess_time,
        "warm_time": warm_time,
        "adjusted_time_limit_given_to_solver": adjusted_time_limit,
        "pulp_status": lp_status,
        "pulp_status_code": int(prob.status)
    }
    return result, meta

if __name__ == '__main__':
    # simple driver: iterate combinations (nota: passiamo presolve correttamente)
    # seed used ofr tests = 0,1234567,26,42,262626,424242,878641,5656565
    bests = [
        (18, "CBC", "balanced", True, 424242, "random_half"),
        (18,"CBC","feasible",True,262626,"week1"),
        # (12,"GLPK","balanced",True,26,""),
        # (12,"GLPK","feasible",True,26,"")
    ]
    for n,solver, objective, presolve, seed, warm_start in bests:
                            # for nn in range(4, n+1, 2):
                                nn = n
                                res_dir = os.path.join(os.path.dirname(__file__), "..", "..", "res", "MIP", "ciao_2")
                                os.makedirs(res_dir, exist_ok=True)
                                out_path = os.path.join(res_dir, f"{nn}.json")
                                global_start = time.time()
                                try:
                                    result, meta = build_model_with_permutations(
                                        n=nn, time_limit=300, seed=seed,
                                              presolve=presolve, warm_start=warm_start,
                                              objective=objective, solver=solver, DEBUG = True)
                                except Exception as e:
                                    print(e)
                                    print(f"[ERROR] n={nn} v=preprocessing obj={objective} seed={seed} presolve={presolve}: {e}")
                                    result = {"time":300,"optimal":False,"obj":None,"sol":[]}
                                    meta = {"pulp_status":"error","runtime_sec":0.0}
                                global_end = time.time()
                                total_runtime = global_end - global_start

                                key = ""
                                if solver == "CBC":
                                    key = f"{solver}_prepro_anchor_{objective}_{warm_start}_{seed}"
                                else:
                                    key = f"{solver}_preproc_anchor_{objective}_dual_{seed}"
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


