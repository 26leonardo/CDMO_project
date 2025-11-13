import argparse, tempfile
from utils import *
from models import *
import os


def main():
    # define the arguments of the parser
    ap = argparse.ArgumentParser(description="Parse SMT2 model and update res/SMT/{N}.json")
    ap.add_argument("--solver", default="z3", choices=["z3", "cvc5", 'opti'], help="Solver binary")
    ap.add_argument("--approach", choices=["channeled", "preprocess"], help="approach to use")
    ap.add_argument("--timeout", type=int, default=300, help="Timeout seconds")
    ap.add_argument("--N", type=int, required=False, help="Teams (even). If omitted, inferred.")
    ap.add_argument("--optimize", default='false', choices=["False", "True", 'true', 'false'], help="Optimization is required?")
    ap.add_argument("--outdir", default="res/SMT", help="Output directory")
    ap.add_argument("--seed", default=0, help="Seed")
    args = ap.parse_args()

    # variable and name which will be used later and for the name
    N = args.N
    W=N-1
    P=N//2
    total_time=0
    opt=args.optimize
    seed=args.seed
    if opt in ['true', 'True']:
        approach = f'{args.solver}_{args.approach}_opt'
    else:
        approach = f'{args.solver}_{args.approach}'

    # define the channeled approach
    if args.approach == 'channeled':
        start=time.time()
        formula, Per, Home= channeled_model_no_check(N)
        with Solver(name=args.solver) as solver:
            if args.solver == "cvc5":
                solver.set_option("tlimit", "300000")  # CVC5 uses "tlimit"
            elif args.solver == "z3":
                solver.set_option("timeout", 300000)

            solver.add_assertion(formula)
            result = solver.solve()

            if result:
                status = 'sat'
                model = solver.get_model()
                sol = build_sol(model, N, Per, Home)
            elif result is None:
                status = 'timeout'
            else:
                status = 'unsat'

        if status=='timeout' or (status in ('unknown', 'unsat') ):
            solved = 0
        else:
            solved = 1
        
        total_time = time.time()-start

        if solved != 0:
            Home_values = [[model.get_value(Home[t][w]).is_true() for w in range(W)] for t in range(N)]
            counts = [sum(1 if Home_values[t][w] else 0 for w in range(W)) for t in range(N)]
            obj = int(sum(abs(2 * c - W) for c in counts))
        else:
            # handle timeout/unsat
            pass
        
        if opt in ['true', 'True']:
            while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat') ):
                sol1=sol
                model1=model
                start2=time.time()
                formula, Per, Home = channeled_model_no_check(N)
                with Solver(name=args.solver) as solver:
                    if args.solver == "cvc5":
                        solver.set_option("tlimit", str(300000-total_time))  # CVC5 uses "tlimit"
                    elif args.solver == "z3":
                        solver.set_option("timeout", 300000-total_time)

                    solver.add_assertion(formula)
                    result = solver.solve()
                    if result:
                        status = 'sat'
                        model = solver.get_model()
                        sol = build_sol(model, N, Per, Home)
                    elif result is None:
                        status = 'timeout'
                    else:
                        status = 'unsat'

                
                total_time += time.time()-start2
                Home_values = [[model.get_value(Home[t][w]).is_true() for w in range(W)] for t in range(N)]
                counts = [sum(1 if Home_values[t][w] else 0 for w in range(W)) for t in range(N)]
                obj = int(sum(abs(2 * c - W) for c in counts))


    elif args.approach == 'preprocess':
        start3=time.time()
        formula, Per, Home = preprocess_approach_domains(N)
        

        with Solver(name=args.solver) as solver:
            if args.solver == "cvc5":
                solver.set_option("tlimit", "300000")  # CVC5 uses "tlimit"
            elif args.solver == "z3":
                solver.set_option("timeout", 300000)

            solver.add_assertion(formula)
            result = solver.solve()

            if result:
                status = 'sat'
                model = solver.get_model()
                sol = build_sol(model, N, Per, Home)
            elif result is None:
                status = 'timeout'
            else:
                status = 'unsat'

        if status=='timeout' or (status in ('unknown', 'unsat') ):
            solved = 0
        else:
            solved = 1
        
        total_time = time.time()-start3

        if solved != 0:
            Home_values = [[model.get_value(Home[t][w]).is_true() for w in range(W)] for t in range(N)]
            counts = [sum(1 if Home_values[t][w] else 0 for w in range(W)) for t in range(N)]
            obj = int(sum(abs(2 * c - W) for c in counts))
        else:
            # handle timeout/unsat
            pass


        if opt in ['true', 'True']:
            while solved != 0 and not (status=='timeout' or status in ('unknown', 'unsat')):
                sol1=sol
                model1=model
                start4=time.time()
                formula, Per, Home = preprocess_approach_domains_opt(N, counts, obj)
                with Solver(name=args.solver) as solver:
                    if args.solver == "cvc5":
                        solver.set_option("tlimit", str(int(300000-total_time*1000)))  # CVC5 uses "tlimit"
                    elif args.solver == "z3":
                        solver.set_option("timeout", 300000-total_time*1000)


                    solver.add_assertion(formula)
                    result = solver.solve()
                    if result:
                        status = 'sat'
                        model = solver.get_model()
                        sol = build_sol(model, N, Per, Home)
                    elif result is None:
                        status = 'timeout'
                    else:
                        status = 'unsat'

                
                total_time += time.time()-start4
                Home_values = [[model.get_value(Home[t][w]).is_true() for w in range(W)] for t in range(N)]
                counts = [sum(1 if Home_values[t][w] else 0 for w in range(W)) for t in range(N)]
                obj = int(sum(abs(2 * c - W) for c in counts))


    
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
    
    if (status in ('unknown', 'unsat')) and solved>0:
        N = args.N or 0
        os.makedirs(args.outdir, exist_ok=True)
        Home_values = [[model1.get_value(Home[t][w]).is_true() for w in range(W)] for t in range(N)]
        counts = [sum(1 if Home_values[t][w] else 0 for w in range(W)) for t in range(N)]
        obj = int(sum(abs(2 * c - W) for c in counts))
        outpath = os.path.join(args.outdir, f"{N}.json") if N else os.path.join(args.outdir, "unknownN.json")
        existing = {}
        if os.path.exists(outpath):
            try:
                with open(outpath, "r") as f: existing = json.load(f)
            except Exception: pass
        existing[approach] = {"time": int(total_time), "optimal": True if N==obj else False, "obj": obj, "sol": sol1}
        with open(outpath, "w") as f: json.dump(existing, f)
        print(f"[OK] {approach}_{N} → {outpath}  (time={int(total_time)}s, obj={obj})")
        return

    # Objective: sum_t |2*home_t - W|
    Home_values = [[model.get_value(Home[t][w]).is_true() for w in range(W)] for t in range(N)]
    counts = [sum(1 if Home_values[t][w] else 0 for w in range(W)) for t in range(N)]
    obj = int(sum(abs(2 * c - W) for c in counts))

    # Merge/update JSON
    os.makedirs(args.outdir, exist_ok=True)
    outpath = os.path.join(args.outdir, f"{N}.json") 
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


if __name__ == "__main__":
    main()
