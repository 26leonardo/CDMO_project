import subprocess
import argparse

# define the main function
def main():
    # define the arguments of the parser
    parser = argparse.ArgumentParser(description="SMT main driver for batch / single runs")
    parser.add_argument("--version", type=str, default=None, help="version token: v1, v2, v3, v4, v5, v6 (or none for batch)")
    parser.add_argument("--instance", "--n", dest="n", type=int, default=None, help="n (even)")
    args = parser.parse_args()

    # if both arguments are none then run all the possible versions with all the feasible instances
    if args.version is None and args.n is None:
        print("[INFO] No version specified and instances -> running batch for all possible versions from v1 to v6 with all possible instances")
        for solver in ['z3', 'cvc5', 'opti']:
            for app in ['channeled','preprocess']:
                for n_i in range(4,19,2):
                    #skip the elements which timeout
                    if (n_i>=16 and solver=='cvc5') or (n_i>=14 and solver=='opti' and app=='channeled'):
                        continue
                    print(f'running solver:{solver} on approach {app} with N={n_i}')
                    subprocess.run(['python', 'source/SMT/parser.py', '--solver', solver, '--approach', app, '--N', str(n_i)], text=True)

    
    # if just the version is none then run all the possible versions on the selected instance
    elif args.version is None and args.n is not None:
        n=args.n
        print(f"[INFO] No version specified -> running batch for all possible versions from v1 to v6 with the given instance {n}")
        for solver in ['z3', 'cvc5', 'opti']:
            for app in ['channeled','preprocess']:
                    print(f'running solver:{solver} on approach {app} with N={n}')
                    subprocess.run(['python', 'source/SMT/parser.py', '--solver', solver, '--approach', app, '--N', str(n)], text=True)
    
    # if the version is set then set the selected model
    else:
        if args.version=='v1':
            vers={'solver':'z3', 'model':'channeled'}
        elif args.version=='v2':
            vers={'solver':'z3', 'model':'preprocess'}
        elif args.version=='v3':
            vers={'solver':'cvc5', 'model':'channeled'}
        elif args.version=='v4':
            vers={'solver':'cvc5', 'model':'preprocess'}
        elif args.version=='v5':
            vers={'solver':'opti', 'model':'channeled'}
        elif args.version=='v6':
            vers={'solver':'opti', 'model':'preprocess'}
        solv=vers['solver']
        mod=vers['model']

        # if the instance is not set then run the chosen version on all the possible instances
        if args.n is None:
            print(f"[INFO] No instance specified -> running {args.version} with all the possible instances")
            for n in range(4,19,2):
                print(f'running solver:{solv} on approach {mod} with N={n}')
                subprocess.run(['python', 'source/SMT/parser.py', '--solver', solv, '--approach', mod, '--N', str(n)], text=True)
        
        # if the instance is set then run the chosen version on the chosen instance
        else:
            n=args.n 
            print(f"[INFO] Running {args.version} with n={n}")     
            subprocess.run(['python', 'source/SMT/parser.py', '--solver', solv, '--approach', mod, '--N', str(n)], text=True)


if __name__ == "__main__":
    main()
