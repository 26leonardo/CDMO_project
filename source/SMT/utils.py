import json, time, subprocess, re
from z3 import *
from collections import defaultdict
import shutil

def build_solution_table(opp, hom, per, N, W, P):
    """
    opp[t][w] : int in 1..N (!= t+1)
    hom[t][w] : bool  (True=home, False=away)
    per[t][w] : int in 1..P
    Return: sol[P][W] with each entry [home_team_id, away_team_id] (1-based).
    """
    # rows = periods (1..P), cols = weeks (0..W-1)
    sol = [[None for _ in range(W)] for _ in range(P)]

    # bucket teams by (week, period)
    by_wp = {(w, p): [] for w in range(W) for p in range(1, P+1)}
    for t in range(N):
        for w in range(W):
            p = per[t][w]
            by_wp[(w, p)].append(t)

    # build pairs
    for w in range(W):
        for p in range(1, P+1):
            teams = by_wp[(w, p)]
            if len(teams) != 2:
                raise ValueError(f"Week {w}, Period {p} has {len(teams)} teams (expected 2).")
            a, b = teams  # team indices 0-based
            ha, hb = hom[a][w], hom[b][w]

            if ha and not hb:
                pair = [a+1, b+1]
            elif hb and not ha:
                pair = [b+1, a+1]
            else:
                # This shouldn't happen if you enforced XOR(Home[a,w], Home[b,w]).
                # As a safety fallback, orient using Opp (arbitrary but deterministic).
                if opp[a][w] == b+1 and opp[b][w] == a+1:
                    pair = [a+1, b+1]
                else:
                    raise ValueError(f"Inconsistent Home/Opp at week {w}, period {p}: teams={teams}, "
                                     f"homes=({ha},{hb}), opp=({opp[a][w]},{opp[b][w]})")
            sol[p-1][w] = pair

    # sanity
    for p in range(P):
        for w in range(W):
            h, a = sol[p][w]
            assert 1 <= h <= N and 1 <= a <= N and h != a

    return sol


def z3_to_int_grid(m, Z):
    """Evaluate a 2D array of Int Z3 vars -> Python ints."""
    T, W_ = len(Z), len(Z[0])
    out = [[m.evaluate(Z[t][w]).as_long() for w in range(W_)] for t in range(T)]
    return out


def z3_to_bool_grid(m, Z):
    """Evaluate a 2D array of Bool Z3 vars -> Python bools."""
    T, W_ = len(Z), len(Z[0])
    out = [[is_true(m.evaluate(Z[t][w])) for w in range(W_)] for t in range(T)]
    return out


def build_solution_from_model(m, Opp, Home, Per, N, W, P):
    """Extract Opp/Home/Per from model and return the checker-format sol."""
    opp = z3_to_int_grid(m, Opp)         # Int
    hom = z3_to_bool_grid(m, Home)       # Bool
    per = z3_to_int_grid(m, Per)         # Int
    return build_solution_table(opp, hom, per, N, W, P)


def make_result_json(sol, approach_name="z3_opt", runtime_sec=0, optimal=True, obj_val=None):
    """Pack result dict."""
    data= {
        approach_name: {
            "time": int(runtime_sec),
            "optimal": bool(optimal),
            "obj": (None if obj_val is None else int(obj_val)),
            "sol": sol
        }
    }
    
    return data

def _coerce_lit(sort: str, lit: str):
    s, v = sort.lower(), lit.lower()
    if s == "bool": return v == "true"
    try: return int(lit)
    except ValueError: raise ValueError(f"Unsupported literal for sort {sort}: {lit}")

DEF_FUN_ANY_RE = re.compile(
    r"\s*\(define-fun\s+([A-Za-z0-9_]+)\s+\(\)\s+([A-Za-z0-9_]+)\s+([^)]+)\)",
    re.I | re.DOTALL
)

GET_VAL_PAIR_RE = re.compile(
    r"\s*\(\s*([A-Za-z0-9_]+)\s+(true|false|-?\d+)\s*\)",
    re.I
)

def parse_model(stdout: str) -> dict:
    """
    Return a dict var_name -> (int|bool) value.
    Supports both (define-fun ...) and ((var val)) styles with int/bool.
    """
    vals = {}
    for m in DEF_FUN_ANY_RE.finditer(stdout):
        name, sort, lit = m.group(1), m.group(2), m.group(3)
        vals[name] = _coerce_lit(sort, lit)
    if vals:
        return vals
    for m in GET_VAL_PAIR_RE.finditer(stdout):
        name, tok = m.group(1), m.group(2)
        if tok.lower() in ("true", "false"):
            vals[name] = (tok.lower() == "true")
        else:
            vals[name] = int(tok)
    return vals


# ---------- grid helpers (0-based names only) ----------
def infer_grid_size(varnames, prefix):
    """Var names like Per_t_w with t,w 0-based -> sizes = max+1."""
    tw, pat = [], re.compile(rf"^{re.escape(prefix)}_(\d+)_(\d+)$")
    for v in varnames:
        m = pat.match(v)
        if m: tw.append((int(m.group(1)), int(m.group(2))))
    if not tw: return None, None
    T = max(t for t,_ in tw) + 1
    W = max(w for _,w in tw) + 1
    return T, W

def read_grid(assigns, prefix, T, W, default=None):
    g = [[default for _ in range(W)] for _ in range(T)]
    for t in range(T):
        for w in range(W):
            k = f"{prefix}_{t}_{w}"
            if k in assigns: g[t][w] = assigns[k]
    return g

def as_bool(x):  # accepts bool or 0/1
    return x if isinstance(x, bool) else bool(int(x))

# ---------- reconstruction ----------
def build_sol_from_per_home(T, W, P, Per, Home):
    """
    Per[t][w] in 1..P, Home[t][w] in Bool.
    Returns P×W with 1-based team IDs [home, away].
    """
    sol = [[None for _ in range(W)] for _ in range(P)]
    for w in range(W):
        buckets = defaultdict(list)
        for t in range(T):
            p = Per[t][w]
            if p is None: raise ValueError(f"Missing Per[{t}][{w}]")
            buckets[p].append(t)
        for p in range(1, P+1):
            teams = buckets.get(p, [])
            if len(teams) != 2:
                raise ValueError(f"Week {w}, period {p} has {len(teams)} teams (expected 2).")
            a, b = teams
            ha, hb = as_bool(Home[a][w]), as_bool(Home[b][w])
            sol[p-1][w] = [a+1, b+1] if ha and not hb else [b+1, a+1] if hb and not ha else [a+1, b+1]
    return sol

def build_sol_from_opp_home(T, W, P, Opp, Home, Per=None):
    """
    Opp[t][w] in 1..N. If Per provided (1..P), places each match into its period.
    Returns P×W with 1-based team IDs [home, away].
    """
    sol = [[None for _ in range(W)] for _ in range(P)]
    for w in range(W):
        seen, pairs = set(), []
        for t in range(T):
            if t in seen: continue
            k = Opp[t][w] - 1
            if k == t or not (0 <= k < T): raise ValueError(f"Bad Opp[{t}][{w}]={Opp[t][w]}")
            if k in seen: continue
            seen.update((t,k))
            ha, hb = as_bool(Home[t][w]), as_bool(Home[k][w])
            pairs.append((t,k) if ha and not hb else (k,t) if hb and not ha else (t,k))
        if len(pairs) != T//2: raise ValueError(f"Week {w}: {len(pairs)} matches (expected {T//2}).")

        if Per is not None:
            per_bucket = {}
            for h,a in pairs:
                p = Per[h][w]  # 1..P
                if p is None: raise ValueError(f"Missing Per at week {w}")
                per_bucket[p] = [h+1, a+1]
            for p in range(1, P+1):
                if p not in per_bucket: raise ValueError(f"Week {w}: no match for period {p}.")
                sol[p-1][w] = per_bucket[p]
        else:
            pairs.sort(key=lambda ab: min(ab))
            for p,(h,a) in enumerate(pairs, start=1):
                sol[p-1][w] = [h+1, a+1]
    return sol

# ---------- solver runner ----------
def run_solver(smt_path, solver, timeout_s):
    """
    Run SMT solver with optimized configuration and robust error handling.
    
    Returns:
        tuple: (stdout, stderr, elapsed_time)
        - For timeout: ("timeout", "", actual_timeout_duration)
        - For success: (solver_output, error_output, elapsed_seconds)
    """
    # Determine solver-specific command and optimizations
    solver_name = solver.lower()
    if "z3" in solver_name:
        cmd = [
    solver, "-smt2", smt_path,
    "smt.phase_selection=4",
       'smt.random_seed=0'  # Disable flattening that can vary
]
    
    elif "cvc5" in solver_name:
        cmd = [
            solver, "--lang=smt2", smt_path,
            "--decision=internal",
            "--produce-models",
            '--random-seed=0'
        ]
    elif 'opti' in solver_name:
        cmd=['optimathsat', smt_path]
    
    # Enhanced process execution
    start_time = time.time()
    
    try:
        # Use higher buffer limits for large models
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,  # Small buffer beyond internal timeout
            check=False,
            text=True,
            bufsize=8192,           # Larger buffer for better I/O performance
            env={**os.environ, 'OMP_NUM_THREADS': '1'}  # Single-threaded for consistency
        )
        
        elapsed = time.time() - start_time
        
        # Handle solver-specific timeout indicators
        if result.returncode == 124 or "timeout" in result.stdout.lower():
            return "timeout", result.stderr, elapsed
        
        # Check for memory issues
        if result.returncode == 137 or "memory" in result.stderr.lower():
            return "memout", result.stderr, elapsed
            
        return result.stdout, result.stderr, elapsed
        
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - start_time
        # Try to get partial output if available
        stdout = e.stdout.decode('utf-8') if e.stdout else ""
        stderr = e.stderr.decode('utf-8') if e.stderr else ""
        return "timeout", stderr, elapsed
    
    except (OSError, FileNotFoundError) as e:
        elapsed = time.time() - start_time
        return "error", f"Solver execution failed: {e}", elapsed
    
    except Exception as e:
        elapsed = time.time() - start_time
        return "error", f"Unexpected error: {e}", elapsed


def get_status(stdout: str) -> str:
    """
    Robustly detect solver result from stdout.
    Returns one of: "sat", "unsat", "unknown", "timeout", "unsupported".
    """
    lines = [ln.strip().lower() for ln in stdout.splitlines() if ln.strip()]
    
    if any("unsat" in ln for ln in lines):
        return "unsat"
    if any("timeout" in ln for ln in lines):
        return "timeout"
    if any("sat" in ln for ln in lines):
        return "sat"
    if any("unknown" in ln for ln in lines):
        return "unknown"