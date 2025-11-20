import argparse, tempfile
from utils import *
from models import *
import os

def main():
    # define the arguments of the parser
    ap = argparse.ArgumentParser(description="Parse SMT2 model and update res/SMT/{N}.json")
    ap.add_argument("--solver", default="z3", choices=["z3", "cvc5", 'math', 'opti'], help="Solver binary")
    ap.add_argument("--approach", choices=["channeled", "preprocess"], help="approach to use")
    ap.add_argument("--timeout", type=int, default=300, help="Timeout seconds")
    ap.add_argument("--N", type=int, required=False, help="Teams (even). If omitted, inferred.")
    ap.add_argument("--optimize", default='false', choices=["False", "True", 'true', 'false'], help="Optimization is required?")
    ap.add_argument("--outdir", default="res/SMT", help="Output directory")
    ap.add_argument("--seed", default=0, help="Seed")
    args = ap.parse_args()

    # variable and name which will be used later and for the name
    N = args.N
    total_time=0
    opt=args.optimize
    seed=args.seed
    phase_sel=4
    if opt in ['true', 'True']:
        approach = f'py_{args.solver}_{args.approach}_opt'
    else:
        approach = f'py_{args.solver}_{args.approach}'

    # define the channeled approach
    if args.approach == 'channeled':
        start=time.time()
        s, Per, Home = channeled_model_no_check(N)
        s=s.simplify()
        write_smtlib(s, f'source/{approach}_{N}.smt2')
        with open(f'source/{approach}_{N}.smt2', "a") as f:
            f.write("(get-model)\n")

        # Run the solver
        diff=time.time()-start
        total_time+=int(diff)
        print(total_time)
        stdout, stderr, elapsed = run_solver(f'source/{approach}_{N}.smt2', args.solver, args.timeout-total_time, seed=seed, phase_sel=4)
        # Delete the file after use
        os.remove(f'source/{approach}_{N}.smt2')
        total_time+=int(elapsed)
        status=get_status(stdout)
        print(elapsed)
        if status=='timeout' or status in ('unknown', 'unsat'):
            solved = 0
        else:
            solved = 1
        print(total_time)

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
        
        if opt in ['true', 'True']:
            while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat') ):
                sol1, sol2 = stdout, stderr
                start2=time.time()
                mid=(obj+N)//2
                s, Per, Home = channeled_model_no_check_opt(N, counts, mid)
                s=s.simplify()
                write_smtlib(s, f'source/{approach}_{N}.smt2')
                with open(f'source/{approach}_{N}.smt2', "a") as f:
                    f.write("(get-model)\n")

                # Run the solver
                diff2=time.time()-start2
                total_time+=int(diff2)
                stdout, stderr, elapsed4 = run_solver(f'source/{approach}_{N}.smt2', args.solver, args.timeout-total_time, seed=seed, phase_sel=4)
                os.remove(f'source/{approach}_{N}.smt2')
                total_time += int(elapsed4)

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
        s, Home, Per = preprocess_approach_domains(N)
        write_smtlib(s, f'source/{approach}_{N}.smt2')
        s=s.simplify()
        with open(f'source/{approach}_{N}.smt2', "a") as f:
            f.write("(get-model)\n")

        # Run the solver
        diff3=time.time()-start3
        total_time+=int(diff3)
        stdout, stderr, elapsed = run_solver(f'source/{approach}_{N}.smt2', args.solver, args.timeout-total_time, seed=seed, phase_sel=phase_sel)

        # Delete the file after use
        os.remove(f'source/{approach}_{N}.smt2')
        status=get_status(stdout)
        if status=='timeout' or status in ('unknown', 'unsat'):
            solved = 0
        else:
            solved = 1

        total_time+=int(elapsed)

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


        if opt in ['true', 'True']:
            while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat') ):
                sol1, sol2 = stdout, stderr
                start4=time.time()
                mid=(obj+N)//2
                s, Home, Per = preprocess_approach_domains_opt(N, counts, mid)
                s=s.simplify()
                write_smtlib(s, f'source/{approach}_{N}.smt2')
                with open(f'source/{approach}_{N}.smt2', "a") as f:
                    f.write("(get-model)\n")

                # Run the solver
                diff4=time.time()-start4
                total_time+=int(diff4)
                stdout, stderr, elapsed4 = run_solver(f'source/{approach}_{N}.smt2', args.solver, args.timeout-total_time, seed=seed,phase_sel=phase_sel)
                total_time += int(elapsed4)

                os.remove(f'source/{approach}_{N}.smt2')
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


    #if not assigns:
    #    print(sol1)
    #    print(sol2, file=sys.stderr)
    #    raise SystemExit("Could not parse any variable assignments. Ensure the file does (get-model) or (get-value ...).")

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