import subprocess
import argparse

# define the main function
def main():
    # define the arguments of the parser
    parser = argparse.ArgumentParser(description="SMT main driver for batch / single runs")
    parser.add_argument("--version", type=str, default=None, help="version token: v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, v16, v17, v18, v19, v20, v21, v22, v23, v24 (or none for batch)")
    parser.add_argument("--instance", "--n", dest="n", type=int, default=None, help="n (even)")
    args = parser.parse_args()

    # if both arguments are none then run all the possible versions with all the feasible instances
    if args.version is None and args.n is None:
        print("[INFO] No version specified and instances -> running batch for all possible versions from v1 to v24 with all possible instances", flush=True)
        for pars in ['parser', 'parser2']:
            enc='py smt' if pars=='parser' else 'z3py' 
            for solver in ['z3', 'cvc5', 'opti']:
                for opt in ['false','true']:
                    for n in range(4,23,2):
                        if (solver=='cvc5' and n>=18):
                            continue
                        if opt=='true':
                            print(f'optimizing with solver:{solver} with N={n} and encoding {enc}', flush=True)
                        else:
                            print(f'first solution with solver:{solver} with N={n} and encoding {enc}', flush=True)
                        subprocess.run(['python','-u', f'source/SMT/{pars}.py', '--solver', solver, '--N', str(n), '--optimize', opt], text=True)
    
    # if just the version is none then run all the possible versions on the selected instance
    elif args.version is None and args.n is not None:
        n=args.n
        print(f"[INFO] No version specified -> running batch for all possible versions from v1 to v24 with the given instance {n}", flush=True)
        for pars in ['parser', 'parser2']:
            enc='py smt' if pars=='parser' else 'z3py' 
            for solver in ['z3', 'cvc5', 'opti']:
                for opt in ['false','true']:
                    if opt=='true':
                        print(f'optimizing with solver:{solver} with N={n} and encoding {enc}', flush=True)
                    else:
                        print(f'first solution with solver:{solver} with N={n} and encoding {enc}', flush=True)
                    subprocess.run(['python', '-u',f'source/SMT/{pars}.py', '--solver', solver, '--N', str(n), '--optimize', opt], text=True)
    
    # if the version is set then set the selected model
    elif args.version is not None:
        if args.version=='v1':
            vers={'parser':'parser','solver':'z3', 'opt':'false'}
        elif args.version=='v2':
            vers={'parser':'parser','solver':'z3', 'opt':'true'}
        elif args.version=='v3':
            vers={'parser':'parser','solver':'cvc5','opt':'false'}
        elif args.version=='v4':
            vers={'parser':'parser','solver':'cvc5','opt':'true'}
        elif args.version=='v5':
            vers={'parser':'parser','solver':'opti', 'opt':'false'}
        elif args.version=='v6':
            vers={'parser':'parser','solver':'opti', 'opt':'true'}
        elif args.version=='v7':
            vers={'parser':'parser2','solver':'z3', 'opt':'false'}
        elif args.version=='v8':
            vers={'parser':'parser2','solver':'z3', 'opt':'true'}
        elif args.version=='v9':
            vers={'parser':'parser2','solver':'cvc5','opt':'false'}
        elif args.version=='v10':
            vers={'parser':'parser2','solver':'cvc5','opt':'true'}
        elif args.version=='v11':
            vers={'parser':'parser2','solver':'opti', 'opt':'false'}
        elif args.version=='v12':
            vers={'parser':'parser2','solver':'opti', 'opt':'true'}

        
        solv=vers['solver']
        opt=vers['opt']
        pars=vers['parser']
        enc='py smt' if pars=='parser' else 'z3py' 

        # if the instance is not set then run the chosen version on all the possible instances
        if args.n is None:
            print(f"[INFO] No instance specified -> running {args.version} with all the possible instances", flush=True)
            for n in range(4,23,2):
                if opt=='true':
                    print(f'optimizing with solver:{solv} with N={n} and encoding {enc}', flush=True)
                else:
                    print(f'first solution with solver:{solv} with N={n} and encoding {enc}', flush=True)
                subprocess.run(['python','-u', f'source/SMT/{pars}.py', '--solver', solv, '--N', str(n), '--optimize', opt], text=True)
        
        # if the instance is set then run the chosen version on the chosen instance
        else:
            n=args.n 
            print(f"[INFO] Running {args.version} with n={n}", flush=True)     
            if opt=='true':
                print(f'optimizing with solver:{solv} with N={n} and encoding {enc}', flush=True)
            else:
                print(f'first solution with solver:{solv} with N={n} and encoding {enc}', flush=True)
            subprocess.run(['python', '-u', f'source/SMT/{pars}.py', '--solver', solv, '--N', str(n), '--optimize', opt], text=True)

if __name__ == "__main__":
    main()
