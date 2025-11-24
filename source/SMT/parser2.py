import argparse, tempfile
from utils import *
from models2 import *


def main():
    # define the arguments of the parser
    ap = argparse.ArgumentParser(description="Parse SMT2 model and update res/SMT/{N}.json")
    ap.add_argument("--solver", default="z3", choices=["z3", "cvc5", 'math', 'opti'], help="Solver binary")
    ap.add_argument("--approach", choices=["channeled", "preprocess"], help="approach to use")
    ap.add_argument("--timeout", type=int, default=300, help="Timeout seconds")
    ap.add_argument("--N", type=int, required=False, help="Teams (even). If omitted, inferred.")
    ap.add_argument("--optimize", default='false', choices=["False", "True", 'true', 'false'], help="Optimization is required?")
    ap.add_argument("--outdir", default="res/SMT", help="Output directory")
    ap.add_argument("--seed", default=90, help="Seed")
    args = ap.parse_args()

    # variable and name which will be used later and for the name
    N = args.N
    total_time=0
    opt=args.optimize
    seed=args.seed
    if opt in ['true', 'True']:
        opt=True
        approach = f'{args.solver}_{args.approach}_opt'
    else:
        opt=False
        approach = f'{args.solver}_{args.approach}'
        
    if args.solver=='z3' and N<=14:
        if args.approach=='preprocess':
            phase=4
        else:
            phase=4
    elif args.solver=='z3' and N>14:
        if args.approach=='preprocess':
            phase=5
        else:
            phase=4
    else:
        phase=None

    # define the channeled approach
    if args.approach == 'channeled':
        start=time.time()
        s, Per, Home, Opp = channeled_model_no_check(N)
        s = symmetry_breaking_constraints(N, s, Home, Per, Opp, opt)
        smt = s.to_smt2()
        

        with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
            f.write(f"(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed {seed})\n")
            f.write(smt)
            f.write("(get-model)\n")
            f.flush()
            end=time.time()-start
            total_time+=int(end)
            stdout, stderr, elapsed = run_solver(f.name, args.solver, args.timeout-total_time, seed=seed, phase_sel=phase)
            tmp_path = f.name
        os.remove(tmp_path)

        status=get_status(stdout)
        if status=='timeout' or (status in ('unknown', 'unsat') ):
            solved = 0
        else:
            solved = 1
        
        total_time += int(elapsed)

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
        
        if opt is True:
            while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat') ):
                sol1, sol2 = stdout, stderr
                start3=time.time()
                mid=(N+obj)//2
                s, Per, Home, Opp = channeled_model_no_check(N)
                s, Home = smt_obj_manual(N, Home, mid, counts, s)
                s = symmetry_breaking_constraints(N, s, Home, Per, Opp, opt)
                smt = s.to_smt2()


                with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
                    f.write(f"(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed {seed})\n")
                    f.write(smt)
                    f.write("(get-model)\n")
                    f.flush() 
                    end3=time.time()-start3
                    total_time+=int(end3)
                    stdout, stderr, elapsed3 = run_solver(f.name, args.solver, args.timeout - total_time, seed=seed, phase_sel=phase) 
                    os.remove(f.name)
                total_time += int(elapsed3)

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



    elif args.approach == 'preprocess':
        start3=time.time()
        s, Home, Per, matches = preprocess_approach_domains(N)
        s = symmetry_breaking_constraints_preprocess(N, s, Home, Per, matches)
        smt = s.to_smt2()
        

        with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
            f.write(f"(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed {seed})\n")
            #f.write("(set-option :dpll.branching_cache_phase 2)\n(set-option :dpll.branching_initial_phase 2)\n(set-option :dpll.branching_random_frequency 0.0)\n")
            f.write(smt)
            f.write("(get-model)\n")
            f.flush()
            end3=time.time()-start3
            total_time+=int(end3)
            stdout, stderr, elapsed3 = run_solver(f.name, args.solver, args.timeout-total_time, seed=seed, phase_sel=phase)
            tmp_path = f.name
        os.remove(tmp_path)
        status=get_status(stdout)
        if status=='timeout' or status in ('unknown', 'unsat')  :
            solved = 0
        else:
            solved = 1

        total_time+=int(elapsed3)

        if solved != 0:
            assigns = parse_model(stdout)
            T, W, P = N, N - 1, N // 2
            Home = read_grid(assigns, "Home", T, W, default=False)
            counts = [sum(1 if as_bool(Home[t][w]) else 0 for w in range(W)) for t in range(T)]
            obj = int(sum(abs(2 * c - W) for c in counts))
            #obj-=N
            
            print(counts)
        else:
            # handle timeout/unsat
            pass


        if opt is True:
            while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat') ):
                sol1, sol2 = stdout, stderr
                start4=time.time()
                mid=(obj+N)//2
                s, Home, Per, matches = preprocess_approach_domains(N)
                s, Home = smt_obj_manual(N, Home, mid, counts, s)
                s = symmetry_breaking_constraints_preprocess(N, s, Home, Per, matches)
                smt = s.to_smt2()


                with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
                    f.write(f"(set-logic QF_LIA)\n(set-option :produce-models true)\n(set-option :timeout 300000)\n(set-option :random-seed {seed})\n")
                    #f.write("(set-option :dpll.branching_cache_phase 2)\n(set-option :dpll.branching_initial_phase 2)\n(set-option :dpll.branching_random_frequency 0.0)\n" \
                    #"(set-option :produce-models true) \n (set-option :auto-config false) \n (set-option :sat.cardinality.encoding ordered) \n (set-option :arith.branch_cut_ratio 1)")
                    f.write(smt)
                    f.write("(get-model)\n")
                    f.flush() 
                    end4=time.time()-start4
                    total_time+=int(end4)
                    stdout, stderr, elapsed4 = run_solver(f.name, args.solver, args.timeout - total_time, seed=seed, phase_sel=phase) 
                    os.remove(f.name)
                total_time += int(elapsed4)

                assigns = parse_model(stdout)
                if not assigns:
                    status=get_status(stdout)
                    break
                Per = read_grid(assigns, "Per", T, W, default=None)
                Home = read_grid(assigns, "Home", T, W, default=False)
                counts = [sum(1 if as_bool(Home[t][w]) else 0 for w in range(W)) for t in range(T)]
                obj = int(sum(abs(2 * c - W) for c in counts))
                #obj-=N
                status=get_status(stdout)
                print(counts)

    
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
    #obj-=N

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