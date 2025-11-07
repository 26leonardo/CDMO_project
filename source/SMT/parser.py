import argparse, tempfile
from utils import *
from models import *


def main():
    # define the arguments of the parser
    ap = argparse.ArgumentParser(description="Parse SMT2 model and update res/SMT/{N}.json")
    ap.add_argument("--solver", default="z3", choices=["z3", "cvc5", 'opti'], help="Solver binary")
    ap.add_argument("--approach", choices=["channeled", "preprocess"], help="approach to use")
    ap.add_argument("--timeout", type=int, default=300, help="Timeout seconds")
    ap.add_argument("--N", type=int, required=False, help="Teams (even). If omitted, inferred.")
    ap.add_argument("--outdir", default="res/SMT", help="Output directory")
    args = ap.parse_args()

    # variable and name which will be used later and for the name
    N = args.N
    total_time=0
    approach = f'{args.solver}_{args.approach}'

    # define the channeled approach
    if args.approach == 'channeled':
        start=time.time()
        s, Per, Home, Opp = channeled_model_no_check(N)
        s = symmetry_breaking_constraints(N, s, Home, Per, Opp)
        smt = s.to_smt2()
        

        with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
            f.write("(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed 0)\n")
            f.write("(set-option :dpll.branching_cache_phase 2)\n(set-option :dpll.branching_initial_phase 2)\n(set-option :dpll.branching_random_frequency 0.0)\n")
            f.write(smt)
            f.write("(get-model)\n")
            f.flush()
            end=time.time()-start
            total_time+=end
            stdout, stderr, elapsed = run_solver(f.name, args.solver, args.timeout-total_time)
            tmp_path = f.name
        os.remove(tmp_path)

        status=get_status(stdout)
        if status=='timeout' or (status in ('unknown', 'unsat') ):
            solved = 0
        else:
            solved = 1
        
        total_time += elapsed

        if solved != 0:
            assigns = parse_model(stdout)
            T, W, P = N, N - 1, N // 2
            Home = read_grid(assigns, "Home", T, W, default=False)
            counts = [sum(1 if as_bool(Home[t][w]) else 0 for w in range(W)) for t in range(T)]
            obj = int(sum(abs(2 * c - W) for c in counts))
            print(counts)
        else:
            # handle timeout/unsat
            pass

        while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat') ):
            sol1, sol2 = stdout, stderr
            start2=time.time()
            s, Per, Home, Opp = channeled_model_no_check(N)
            s, Home = smt_obj_manual(N, Home, obj, counts, s)
            s = symmetry_breaking_constraints(N, s, Home, Per, Opp)
            smt = s.to_smt2()

            with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
                f.write("(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed 0)")
                f.write("(set-option :dpll.branching_cache_phase 2)\n(set-option :dpll.branching_initial_phase 2)\n(set-option :dpll.branching_random_frequency 0.0)\n")
                f.write(smt)
                f.write("(get-model)\n")
                f.flush()
                end2=time.time()-start2
                total_time+=end2
                stdout, stderr, elapsed2 = run_solver(f.name, args.solver, max(1, args.timeout - total_time))

                os.remove(f.name)
            total_time += elapsed2
            assigns = parse_model(stdout)
            if not assigns:
                status=get_status(stdout)
                break
            Home = read_grid(assigns, "Home", T, W, default=False)
            counts = [sum(1 if as_bool(Home[t][w]) else 0 for w in range(W)) for t in range(T)]
            obj = int(sum(abs(2 * c - W) for c in counts))
            status=get_status(stdout)
            print(counts)


    elif args.approach == 'preprocess':
        start3=time.time()
        s, Home, Per, matches = preprocess_approach_domains(N)
        s = symmetry_breaking_constraints_preprocess(N, s, Home, Per, matches)
        smt = s.to_smt2()
        

        with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
            f.write("(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed 0)\n")
            f.write("(set-option :dpll.branching_cache_phase 2)\n(set-option :dpll.branching_initial_phase 2)\n(set-option :dpll.branching_random_frequency 0.0)\n")
            f.write(smt)
            f.write("(get-model)\n")
            f.flush()
            end3=time.time()-start3
            total_time+=end3
            stdout, stderr, elapsed3 = run_solver(f.name, args.solver, args.timeout-total_time)
            tmp_path = f.name
        os.remove(tmp_path)

        status=get_status(stdout)
        if status=='timeout' or status in ('unknown', 'unsat')  :
            solved = 0
        else:
            solved = 1

        total_time+=elapsed3+end3

        if solved != 0:
            assigns = parse_model(stdout)
            T, W, P = N, N - 1, N // 2
            Home = read_grid(assigns, "Home", T, W, default=False)
            counts = [sum(1 if as_bool(Home[t][w]) else 0 for w in range(W)) for t in range(T)]
            obj = int(sum(abs(2 * c - W) for c in counts))
            
            print(counts)
        else:
            # handle timeout/unsat
            pass

        while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat') ):
            sol1, sol2 = stdout, stderr
            start4=time.time()
            s, Home, Per, matches = preprocess_approach_domains(N)
            s, Home = smt_obj_manual(N, Home, obj, counts, s)
            s = symmetry_breaking_constraints_preprocess(N, s, Home, Per, matches)
            smt = s.to_smt2()
           

            with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
                f.write("(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed 0)\n")
                f.write("(set-option :dpll.branching_cache_phase 2)\n(set-option :dpll.branching_initial_phase 2)\n(set-option :dpll.branching_random_frequency 0.0)\n")
                f.write(smt)
                f.write("(get-model)\n")
                f.flush() 
                end4=time.time()-start4
                total_time+=end4
                stdout, stderr, elapsed4 = run_solver(f.name, args.solver, args.timeout - total_time) 
                os.remove(f.name)
            total_time += elapsed4

            assigns = parse_model(stdout)
            if not assigns:
                status=get_status(stdout)
                break
            Per = read_grid(assigns, "Per", T, W, default=None)
            Home = read_grid(assigns, "Home", T, W, default=False)
            counts = [sum(1 if as_bool(Home[t][w]) else 0 for w in range(W)) for t in range(T)]
            obj = int(sum(abs(2 * c - W) for c in counts))
            status=get_status(stdout)
            print(counts)

    # ... (rest of your code for timeout/unsat handling, solution reconstruction, JSON writing)
    if status=='timeout' and solved==0:
        N = args.N or 0
        os.makedirs(args.outdir, exist_ok=True)
        outpath = os.path.join(args.outdir, f"{N}.json") if N else os.path.join(args.outdir, "unknownN.json")
        existing = {}
        if os.path.exists(outpath):
            try:
                with open(outpath, "r") as f: existing = json.load(f)
            except Exception: pass
        existing[approach] = {"time": int(total_time), "optimal": False, "obj": None, "sol": []}
        with open(outpath, "w") as f: json.dump(existing, f)
        print(f"[TIMEOUT] merged placeholder into {outpath}")
        return

    if (status in ('unknown', 'unsat')) and solved==0:
        N = args.N or 0
        os.makedirs(args.outdir, exist_ok=True)
        outpath = os.path.join(args.outdir, f"{N}.json") if N else os.path.join(args.outdir, "unknownN.json")
        existing = {}
        if os.path.exists(outpath):
            try:
                with open(outpath, "r") as f: existing = json.load(f)
            except Exception: pass
        existing[approach] = {"time": int(total_time), "optimal": True, "obj": None, "sol": []}
        with open(outpath, "w") as f: json.dump(existing, f)
        print(f"[UNSAT] merged placeholder into {outpath}")
        return


    if (status=='timeout' or status in ('unknown', 'unsat') ) and solved>0:
        assigns = parse_model(sol1)
        Per  = read_grid(assigns, "Per",  T, W, default=None)
        Home = read_grid(assigns, "Home", T, W, default=False)
        Opp=None


    if not assigns:
        print(sol1)
        print(sol2, file=sys.stderr)
        raise SystemExit("Could not parse any variable assignments. Ensure the file does (get-model) or (get-value ...).")

    # Reconstruct solution
    try:
        Per = read_grid(assigns, "Per", T, W, default=None)
        Home = read_grid(assigns, "Home", T, W, default=False)
        Opp=None
        if Opp is not None:
            sol = build_sol_from_opp_home(T, W, P, Opp, Home, Per)
        else:
            if Per is None:
                raise ValueError("Need either Opp or Per to reconstruct matches.")
            sol = build_sol_from_per_home(T, W, P, Per, Home)
    except Exception as e:
        os.makedirs(args.outdir, exist_ok=True)
        outpath = os.path.join(args.outdir, f"{T}.json")
        payload = {approach: {"time": int(args.timeout), "optimal": False, "obj": None, "sol": []}}
        with open(outpath, "w") as f: json.dump(payload, f)
        raise SystemExit(f"[ERROR] {e}\nWrote placeholder {outpath}")

    # Objective: sum_t |2*home_t - W|
    counts = [sum(1 if as_bool(Home[t][w]) else 0 for w in range(W)) for t in range(T)]
    obj = int(sum(abs(2*c - W) for c in counts))

    # Merge/update JSON
    os.makedirs(args.outdir, exist_ok=True)
    outpath = os.path.join(args.outdir, f"{T}.json") 
    try:
        with open(outpath, "r") as f:
            existing = json.load(f)
    except Exception:
        existing = {}

    existing[approach] = {
        "time": int(total_time),
        "optimal": True if obj==N else False,
        "obj": obj,
        "sol": sol
    }
    with open(outpath, "w") as f:
        json.dump(existing, f)
    print(f"[OK] {approach}_{N} → {outpath}  (time={int(total_time)}s, obj={obj})")
    print(counts)


if __name__ == "__main__":
    main()
