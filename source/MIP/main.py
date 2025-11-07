#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
source/MIP/main.py

Driver that orchestrates running the MIP variants v_1_2_3.py and v_4.py
according to the rules you specified.

Usage examples (entrypoint will call this):
  # batch mode (no args)
  python source/MIP/main.py

  # single-version mode (example v1, n=8)
  python source/MIP/main.py --version v1 --instance 8

The script expects that v_1_2_3.py exposes a function:
    build_model(n, solver, time_limit, seed, presolve, version, sym_flags, objective, warm_start, cuts)
and that v_4.py exposes:
    build_model_with_permutations(n, time_limit, seed, presolve, warm_start, objective, solver)

If those functions are absent, the script will try to execute the module as fallback.
"""

import os
import sys
import time
import json
import traceback
import importlib.util

HERE = os.path.dirname(__file__)

# ---- Helpers -----------------------------------------------------------------
def import_module(path):
    """Import a module from a filesystem path and return it."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(os.path.basename(path), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def safe_int(x):
    try:
        return int(x)
    except Exception:
        return None

def write_merge_json(out_path, key, result):
    """Merge the result under key into JSON file out_path (create if missing)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    old = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r") as f:
                old = json.load(f)
                if not isinstance(old, dict):
                    old = {}
        except (ValueError, json.JSONDecodeError):
            old = {}
    old.update({key: result})
    with open(out_path, "w") as f:
        json.dump(old, f, indent=2)

def make_default_result():
    return {"time": 300, "optimal": False, "obj": None, "sol": []}

# ---- Predefined best-lists (from your description) ---------------------------
V123_BESTS = [
    # (n_max, solver, version, objective, seed, presolve, sym_flags, warm_start, cuts)
    (14, "CBC", "base",  "feasible", 42, True,  "",      "week1", False),
    (14, "CBC", "i<j",   "balanced", 878641, True, "",      "week1", False),
    (12, "GLPK","base",  "feasible", 26, True,  "B",     "",      False),
    (10, "GLPK","i<j",   "balanced", 26, True,  "A",     "",      True),
]

V4_BESTS = [
    # (n_max, solver, objective, presolve, seed, warm_start)
    (16, "CBC", "balanced", True, 424242, "random_half"),
    (16, "CBC", "feasible", True, 262626, "week1"),
    (12, "GLPK","balanced", True, 26, ""),
    (14, "GLPK","feasible", True, 26, ""),
]


# ---- Core runner functions ---------------------------------------------------
def run_v123_batch(module_v123):
    """
    Run the v_1_2_3 bests as in your snippet.
    Results are written to res/MIP/{nn}.json
    """
    for n_max, solver, version, objective, seed, presolve, sym_flags, warm_start, cuts in V123_BESTS:
        for nn in range(4, n_max + 1, 2):
            res_dir = os.path.join(HERE, "..", "..", "res", "MIP")
            os.makedirs(res_dir, exist_ok=True)
            out_path = os.path.join(res_dir, f"{nn}.json")
            global_start = time.time()
            try:
                # call build_model as required
                if hasattr(module_v123, "build_model"):
                    result_meta = module_v123.build_model(
                        nn,
                        solver=solver,
                        time_limit=300,
                        seed=seed,
                        presolve=presolve,
                        version=version,
                        sym_flags=sym_flags,
                        objective=objective,
                        warm_start=warm_start,
                        cuts=cuts
                    )
                    # build_model may return (result, meta) or just result
                    if isinstance(result_meta, tuple) and len(result_meta) == 2:
                        result, meta = result_meta
                    else:
                        result = result_meta
                        meta = {"pulp_status": "ok", "runtime_sec": 0.0}
                else:
                    # fallback: execute module as script (it might implement its own driver)
                    print(f"[WARN] module v_1_2_3 has no build_model; executing as script fallback for nn={nn}")
                    import runpy
                    runpy.run_path(os.path.join(os.path.dirname(module_v123.__file__), "v_1_2_3.py"), run_name="__main__")
                    result = make_default_result()
                    meta = {"pulp_status":"ran_script", "runtime_sec": 0.0}
            except Exception as e:
                print(f"[ERROR] n={nn} v={version} obj={objective} seed={seed} presolve={presolve}: {e}")
                traceback.print_exc()
                result = {"time": 300, "optimal": False, "obj": None, "sol": []}
                meta = {"pulp_status":"error","runtime_sec":0.0}
            global_end = time.time()
            total_runtime = global_end - global_start

            # compute key as specified
            if solver == "CBC":
                key = f"{solver}_{version}_{objective}_{warm_start}_{sym_flags}_{seed}"
            else:
                if cuts:
                    key = f"{solver}_{version}_{objective}_dual_cuts_{sym_flags}_{seed}"
                else:
                    key = f"{solver}_{version}_{objective}_dual_{sym_flags}_{seed}"

            # Logging
            print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
            print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
            print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result.get('time')})")

            # Merge and write
            try:
                write_merge_json(out_path, key, result)
            except Exception as e:
                print(f"[ERROR] writing json {out_path}: {e}")
                traceback.print_exc()


# -----------------------------
# New single-version runners
# -----------------------------

def run_v2_single(n, module_v123):
    """
    v2: Run two CBC cases using v_1_2_3.build_model:
      ("CBC","base","feasible",42,True,"","week1",False)
      ("CBC","base","balanced",42,True,"","week1",False)

    Writes results to res/additional_tests/{n}.json (merged keys).
    """
    cases = [
        (n, "CBC", "i!=j",  "feasible", 42, True,  "",      "week1", False),
        (n, "CBC", "i!=j",  "balanced", 42, True,  "",      "week1", False),
    ]
    out_dir = os.path.join(HERE, "..", "..", "res", "additional_tests")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{n}.json")

    for (nn, solver, version, objective, seed, presolve, sym_flags, warm_start, cuts) in cases:
        global_start = time.time()
        try:
            if hasattr(module_v123, "build_model"):
                result_meta = module_v123.build_model(
                    nn, solver=solver, time_limit=300, seed=seed, presolve=presolve,
                    version=version, sym_flags=sym_flags, objective=objective,
                    warm_start=warm_start, cuts=cuts
                )
                if isinstance(result_meta, tuple) and len(result_meta) == 2:
                    result, meta = result_meta
                else:
                    result = result_meta
                    meta = {"pulp_status":"ok","runtime_sec":0.0}
            else:
                # fallback: execute the module script (unlikely for v_1_2_3)
                import runpy
                runpy.run_path(os.path.join(os.path.dirname(module_v123.__file__), "v_1_2_3.py"), run_name="__main__")
                result = make_default_result()
                meta = {"pulp_status":"ran_script","runtime_sec":0.0}
        except Exception as e:
            print(f"[ERROR] v2 single run n={nn} solver={solver}: {e}")
            traceback.print_exc()
            result = make_default_result()
            meta = {"pulp_status":"error","runtime_sec":0.0}
        global_end = time.time()
        total_runtime = global_end - global_start

        # build key (same pattern as other runners)
        if solver == "CBC":
            key = f"{solver}_{version}_{objective}_{warm_start}_{sym_flags}_{seed}"
        else:
            if cuts:
                key = f"{solver}_{version}_{objective}_dual_cuts_{sym_flags}_{seed}"
            else:
                key = f"{solver}_{version}_{objective}_dual_{sym_flags}_{seed}"

        print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
        print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
        print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result.get('time')})")

        try:
            write_merge_json(out_path, key, result)
        except Exception as e:
            print(f"[ERROR] writing v2 json: {e}")
            traceback.print_exc()


def run_v5_single(n, module_v123):
    """
    v5: Run multiple seeds to show variation across seeds.
    Cases: for each seed in SEEDS run ("CBC","base","feasible", seed, False, "", "", False)
    Output merges to res/additional_tests/{n}.json
    """
    SEEDS = [0, 1234567, 26, 42, 262626, 424242, 878641, 5656565]
    cases = [(n, "CBC", "base", "feasible", s, False, "", "", False) for s in SEEDS]

    out_dir = os.path.join(HERE, "..", "..", "res", "additional_tests")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{n}.json")

    for (nn, solver, version, objective, seed, presolve, sym_flags, warm_start, cuts) in cases:
        global_start = time.time()
        try:
            if hasattr(module_v123, "build_model"):
                result_meta = module_v123.build_model(
                    nn, solver=solver, time_limit=300, seed=seed, presolve=presolve,
                    version=version, sym_flags=sym_flags, objective=objective,
                    warm_start=warm_start, cuts=cuts
                )
                if isinstance(result_meta, tuple) and len(result_meta) == 2:
                    result, meta = result_meta
                else:
                    result = result_meta
                    meta = {"pulp_status":"ok","runtime_sec":0.0}
            else:
                import runpy
                runpy.run_path(os.path.join(os.path.dirname(module_v123.__file__), "v_1_2_3.py"), run_name="__main__")
                result = make_default_result()
                meta = {"pulp_status":"ran_script","runtime_sec":0.0}
        except Exception as e:
            print(f"[ERROR] v5 single run n={nn} solver={solver} seed={seed}: {e}")
            traceback.print_exc()
            result = make_default_result()
            meta = {"pulp_status":"error","runtime_sec":0.0}

        global_end = time.time()
        total_runtime = global_end - global_start

        if solver == "CBC":
            key = f"{solver}_{version}_{objective}_{warm_start}_{sym_flags}_{seed}"
        else:
            if cuts:
                key = f"{solver}_{version}_{objective}_dual_cuts_{sym_flags}_{seed}"
            else:
                key = f"{solver}_{version}_{objective}_dual_{sym_flags}_{seed}"

        print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
        print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
        print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result.get('time')})")

        try:
            write_merge_json(out_path, key, result)
        except Exception as e:
            print(f"[ERROR] writing v5 json: {e}")
            traceback.print_exc()


def run_v6_single(n, module_v123, module_v4):
    """
    v6: combine GLPK experiments over seeds and whether cuts enabled, for both
        base and i<j variants; also run a couple GLPK cases via v_4 preprocessing.
    - For v_1_2_3 runs:
        ("GLPK","base","feasible", seed, True, "B", "", cuts)
        ("GLPK","i<j","balanced", seed, True, "A", "", cuts)
      with seeds [26, 42] and cuts in {False, True}.
    - For v_4 runs: two GLPK preprocessing cases (balanced and feasible) with seed 26.
    Results merged to res/additional_tests/{n}.json
    """
    seeds = [26, 42]
    cuts_options = [False, True]

    out_dir = os.path.join(HERE, "..", "..", "res", "additional_tests")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{n}.json")

    # v_1_2_3 GLPK combinations
    for seed in seeds:
        for cuts in cuts_options:
            # base
            try:
                global_start = time.time()
                if hasattr(module_v123, "build_model"):
                    result_meta = module_v123.build_model(
                        n, solver="GLPK", time_limit=300, seed=seed, presolve=True,
                        version="base", sym_flags="B", objective="feasible",
                        warm_start="", cuts=cuts
                    )
                    if isinstance(result_meta, tuple) and len(result_meta) == 2:
                        result, meta = result_meta
                    else:
                        result = result_meta
                        meta = {"pulp_status":"ok","runtime_sec":0.0}
                else:
                    import runpy
                    runpy.run_path(os.path.join(os.path.dirname(module_v123.__file__), "v_1_2_3.py"), run_name="__main__")
                    result = make_default_result()
                    meta = {"pulp_status":"ran_script","runtime_sec":0.0}
            except Exception as e:
                print(f"[ERROR] v6 base GLPK n={n} seed={seed} cuts={cuts}: {e}")
                traceback.print_exc()
                result = make_default_result()
                meta = {"pulp_status":"error","runtime_sec":0.0}
            global_end = time.time()
            total_runtime = global_end - global_start

            if "GLPK" == "CBC":
                key = f"GLPK_base_feasible_{''}_{''}_{seed}"
            else:
                # follow previously used key pattern for GLPK (dual/_cuts)
                if cuts:
                    key = f"GLPK_base_feasible_dual_cuts_B_{seed}"
                else:
                    key = f"GLPK_base_feasible_dual_B_{seed}"

            print(f"[DONE] n={n} approach= {key} presolve={True} seed={seed} -> {out_path}")
            print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
            print(f"Runtime (total) = {total_runtime:.2f}s (time field written: {result.get('time')})")

            try:
                write_merge_json(out_path, key, result)
            except Exception as e:
                print(f"[ERROR] writing v6 base json: {e}")
                traceback.print_exc()

            # i<j variant
            try:
                global_start = time.time()
                if hasattr(module_v123, "build_model"):
                    result_meta = module_v123.build_model(
                        n, solver="GLPK", time_limit=300, seed=seed, presolve=True,
                        version="i<j", sym_flags="A", objective="balanced",
                        warm_start="", cuts=cuts
                    )
                    if isinstance(result_meta, tuple) and len(result_meta) == 2:
                        result, meta = result_meta
                    else:
                        result = result_meta
                        meta = {"pulp_status":"ok","runtime_sec":0.0}
                else:
                    import runpy
                    runpy.run_path(os.path.join(os.path.dirname(module_v123.__file__), "v_1_2_3.py"), run_name="__main__")
                    result = make_default_result()
                    meta = {"pulp_status":"ran_script","runtime_sec":0.0}
            except Exception as e:
                print(f"[ERROR] v6 i<j GLPK n={n} seed={seed} cuts={cuts}: {e}")
                traceback.print_exc()
                result = make_default_result()
                meta = {"pulp_status":"error","runtime_sec":0.0}
            global_end = time.time()
            total_runtime = global_end - global_start

            if cuts:
                key = f"GLPK_i<j_balanced_dual_cuts_A_{seed}"
            else:
                key = f"GLPK_i<j_balanced_dual_A_{seed}"

            print(f"[DONE] n={n} approach= {key} presolve={True} seed={seed} -> {out_path}")
            print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
            print(f"Runtime (total) = {total_runtime:.2f}s (time field written: {result.get('time')})")

            try:
                write_merge_json(out_path, key, result)
            except Exception as e:
                print(f"[ERROR] writing v6 i<j json: {e}")
                traceback.print_exc()

    # v_4 GLPK preprocessing cases (two cases)
    v4_cases = [
        (n, "GLPK", "balanced", True, 26, ""),
        (n, "GLPK", "feasible", True, 26, "")
    ]
    if module_v4 is not None:
        for (nn, solver, objective, presolve, seed, warm_start) in v4_cases:
            global_start = time.time()
            try:
                if hasattr(module_v4, "build_model_with_permutations"):
                    result_meta = module_v4.build_model_with_permutations(
                        n=nn,
                        time_limit=300,
                        seed=seed,
                        presolve=presolve,
                        warm_start=warm_start,
                        objective=objective,
                        solver=solver
                    )
                    if isinstance(result_meta, tuple) and len(result_meta) == 2:
                        result, meta = result_meta
                    else:
                        result = result_meta
                        meta = {"pulp_status":"ok","runtime_sec":0.0}
                else:
                    import runpy
                    runpy.run_path(os.path.join(os.path.dirname(module_v4.__file__), "v_4.py"), run_name="__main__")
                    result = make_default_result()
                    meta = {"pulp_status":"ran_script","runtime_sec":0.0}
            except Exception as e:
                print(f"[ERROR] v6 v4 preprocessing n={nn} solver={solver}: {e}")
                traceback.print_exc()
                result = make_default_result()
                meta = {"pulp_status":"error","runtime_sec":0.0}
            global_end = time.time()
            total_runtime = global_end - global_start

            if solver == "CBC":
                key = f"{solver}_preprocessing_{objective}_{warm_start}_{seed}"
            else:
                key = f"{solver}_preprocessing_{objective}_dual_{seed}"

            print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
            print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
            print(f"Runtime (total) = {total_runtime:.2f}s (time field written: {result.get('time')})")

            try:
                write_merge_json(out_path, key, result)
            except Exception as e:
                print(f"[ERROR] writing v6 v4 json: {e}")
                traceback.print_exc()




def run_v4_batch(module_v4):
    """
    Run the v_4 bests as in your snippet.
    Results are written to res/MIP/{nn}.json
    """
    for n_max, solver, objective, presolve, seed, warm_start in V4_BESTS:
        for nn in range(4, n_max + 1, 2):
            res_dir = os.path.join(HERE, "..", "..", "res", "MIP")
            os.makedirs(res_dir, exist_ok=True)
            out_path = os.path.join(res_dir, f"{nn}.json")
            global_start = time.time()
            try:
                if hasattr(module_v4, "build_model_with_permutations"):
                    result_meta = module_v4.build_model_with_permutations(
                        n=nn,
                        time_limit=300,
                        seed=seed,
                        presolve=presolve,
                        warm_start=warm_start,
                        objective=objective,
                        solver=solver
                    )
                    if isinstance(result_meta, tuple) and len(result_meta) == 2:
                        result, meta = result_meta
                    else:
                        result = result_meta
                        meta = {"pulp_status":"ok","runtime_sec":0.0}
                else:
                    print(f"[WARN] v_4 has no build_model_with_permutations; running script fallback for nn={nn}")
                    import runpy
                    runpy.run_path(os.path.join(os.path.dirname(module_v4.__file__), "v_4.py"), run_name="__main__")
                    result = make_default_result()
                    meta = {"pulp_status":"ran_script","runtime_sec":0.0}
            except Exception as e:
                print(f"[ERROR] n={nn} v=preprocessing obj={objective} seed={seed} presolve={presolve}: {e}")
                traceback.print_exc()
                result = {"time": 300, "optimal": False, "obj": None, "sol": []}
                meta = {"pulp_status":"error","runtime_sec":0.0}
            global_end = time.time()
            total_runtime = global_end - global_start

            # compute key for preprocessing as specified
            if solver == "CBC":
                key = f"{solver}_prepro_anchor_{objective}_{warm_start}_{seed}"
            else:
                key = f"{solver}_preproc_anchor_{objective}_dual_{seed}"

            # Logging
            print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
            print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
            print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result.get('time')})")

            # Merge and write
            try:
                write_merge_json(out_path, key, result)
            except Exception as e:
                print(f"[ERROR] writing json {out_path}: {e}")
                traceback.print_exc()

# ---- Single-version (additional_tests) runners --------------------------------
def run_v1_single(n, module_v123):
    """
    For version v1 and given n run the two specified configurations:
      (n,"CBC","base","feasible",42,True,"","week1",False)
      (n,"GLPK","base","feasible",26,True,"B","",False)
    Save outputs to res/additional_tests/{n}.json (merged keys).
    """
    cases = [
        (n, "CBC", "base",  "feasible", 42, True,  "",      "week1", False),
        (n, "GLPK","base",  "feasible", 26, True,  "B",     "",      False),
    ]
    out_dir = os.path.join(HERE, "..", "..", "res", "additional_tests")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{n}.json")

    for (nn, solver, version, objective, seed, presolve, sym_flags, warm_start, cuts) in cases:
        global_start = time.time()
        try:
            if hasattr(module_v123, "build_model"):
                result_meta = module_v123.build_model(
                    nn, solver=solver, time_limit=300, seed=seed, presolve=presolve,
                    version=version, sym_flags=sym_flags, objective=objective,
                    warm_start=warm_start, cuts=cuts
                )
                if isinstance(result_meta, tuple) and len(result_meta) == 2:
                    result, meta = result_meta
                else:
                    result = result_meta
                    meta = {"pulp_status":"ok","runtime_sec":0.0}
            else:
                print("[WARN] build_model not found in v_1_2_3, running fallback")
                import runpy
                runpy.run_path(os.path.join(os.path.dirname(module_v123.__file__), "v_1_2_3.py"), run_name="__main__")
                result = make_default_result()
                meta = {"pulp_status":"ran_script","runtime_sec":0.0}
        except Exception as e:
            print(f"[ERROR] single v1 run n={nn} solver={solver}: {e}")
            traceback.print_exc()
            result = make_default_result()
            meta = {"pulp_status":"error","runtime_sec":0.0}
        global_end = time.time()
        total_runtime = global_end - global_start

        # construct key same as earlier logic
        if solver == "CBC":
            key = f"{solver}_{version}_{objective}_{warm_start}_{sym_flags}_{seed}"
        else:
            if cuts:
                key = f"{solver}_{version}_{objective}_dual_cuts_{sym_flags}_{seed}"
            else:
                key = f"{solver}_{version}_{objective}_dual_{sym_flags}_{seed}"

        print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
        print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
        print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result.get('time')})")

        try:
            write_merge_json(out_path, key, result)
        except Exception as e:
            print(f"[ERROR] writing single v1 json: {e}")
            traceback.print_exc()

def run_v3_single(n, module_v123):
    """
    For version v3 (i<j) and given n run two specific configurations:
      (n,"CBC","i<j","balanced",878641,True,"","week1",False)
      (n,"GLPK","i<j","balanced",26,True,"A","",True)
    Save outputs to res/additional_tests/{n}.json
    """
    cases = [
        (n, "CBC", "i<j", "balanced", 878641, True,  "",      "week1", False),
        (n, "GLPK","i<j", "balanced", 26,     True,  "A",     "",      True),
    ]
    out_dir = os.path.join(HERE, "..", "..", "res", "additional_tests")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{n}.json")

    for (nn, solver, version, objective, seed, presolve, sym_flags, warm_start, cuts) in cases:
        global_start = time.time()
        try:
            if hasattr(module_v123, "build_model"):
                result_meta = module_v123.build_model(
                    nn, solver=solver, time_limit=300, seed=seed, presolve=presolve,
                    version=version, sym_flags=sym_flags, objective=objective,
                    warm_start=warm_start, cuts=cuts
                )
                if isinstance(result_meta, tuple) and len(result_meta) == 2:
                    result, meta = result_meta
                else:
                    result = result_meta
                    meta = {"pulp_status":"ok","runtime_sec":0.0}
            else:
                print("[WARN] build_model not found in v_1_2_3, running fallback")
                import runpy
                runpy.run_path(os.path.join(os.path.dirname(module_v123.__file__), "v_1_2_3.py"), run_name="__main__")
                result = make_default_result()
                meta = {"pulp_status":"ran_script","runtime_sec":0.0}
        except Exception as e:
            print(f"[ERROR] single v3 run n={nn} solver={solver}: {e}")
            traceback.print_exc()
            result = make_default_result()
            meta = {"pulp_status":"error","runtime_sec":0.0}
        global_end = time.time()
        total_runtime = global_end - global_start

        if solver == "CBC":
            key = f"{solver}_{version}_{objective}_{warm_start}_{sym_flags}_{seed}"
        else:
            if cuts:
                key = f"{solver}_{version}_{objective}_dual_cuts_{sym_flags}_{seed}"
            else:
                key = f"{solver}_{version}_{objective}_dual_{sym_flags}_{seed}"

        print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
        print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
        print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result.get('time')})")

        try:
            write_merge_json(out_path, key, result)
        except Exception as e:
            print(f"[ERROR] writing single v3 json: {e}")
            traceback.print_exc()

def run_v4_single(n, module_v4):
    """
    For version v4 and given n run two configurations (chosen as "analogous"):
        (n, "CBC", "balanced", True, 42, "random_half"),
        (n, "CBC", "feasible", True, 26, "week1"),
        (n, "GLPK","balanced", True, 26, ""),
        (n, "GLPK","feasible", True, 26, "")
    Save outputs to res/additional_tests/{n}.json
    """
    cases = [
        (n, "CBC", "balanced", True, 424242, "random_half"),
        (n, "CBC", "feasible", True, 262626, "week1"),
        (n, "GLPK","balanced", True, 26, ""),
        (n, "GLPK","feasible", True, 26, "")
    ]
    out_dir = os.path.join(HERE, "..", "..", "res", "additional_tests")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{n}.json")

    for (nn, solver, objective, presolve, seed, warm_start) in cases:
        global_start = time.time()
        try:
            if hasattr(module_v4, "build_model_with_permutations"):
                result_meta = module_v4.build_model_with_permutations(
                    n=nn,
                    time_limit=300,
                    seed=seed,
                    presolve=presolve,
                    warm_start=warm_start,
                    objective=objective,
                    solver=solver
                )
                if isinstance(result_meta, tuple) and len(result_meta) == 2:
                    result, meta = result_meta
                else:
                    result = result_meta
                    meta = {"pulp_status":"ok","runtime_sec":0.0}
            else:
                print("[WARN] v_4 has no build_model_with_permutations; running fallback script")
                import runpy
                runpy.run_path(os.path.join(os.path.dirname(module_v4.__file__), "v_4.py"), run_name="__main__")
                result = make_default_result()
                meta = {"pulp_status":"ran_script","runtime_sec":0.0}
        except Exception as e:
            print(f"[ERROR] single v4 run n={nn} solver={solver}: {e}")
            traceback.print_exc()
            result = make_default_result()
            meta = {"pulp_status":"error","runtime_sec":0.0}
        global_end = time.time()
        total_runtime = global_end - global_start

        if solver == "CBC":
            key = f"{solver}_preprocessing_{objective}_{warm_start}_{seed}"
        else:
            key = f"{solver}_preprocessing_{objective}_dual_{seed}"

        print(f"[DONE] n={nn} approach= {key} presolve={presolve} seed={seed} -> {out_path}")
        print(f"Status: {meta.get('pulp_status','?')} | optimal={result.get('optimal',False)} | obj={result.get('obj',None)}")
        print(f"Runtime (total, incl. 'presolve') = {total_runtime:.2f}s (time field written: {result.get('time')})")

        try:
            write_merge_json(out_path, key, result)
        except Exception as e:
            print(f"[ERROR] writing single v4 json: {e}")
            traceback.print_exc()

# ---- Entry point ------------------------------------------------------------
def main():
    """
    If no args -> run batch for both v_1_2_3 and v_4
    If args -> expects --version <v1|v3|v4> --instance <n>
    (we accept also -h / --help)
    """
    import argparse
    parser = argparse.ArgumentParser(description="MIP main driver for batch / single runs")
    parser.add_argument("--version", type=str, default=None, help="version token: v1, v3, v4 (or none for batch)")
    parser.add_argument("--instance", "--n", dest="n", type=int, default=None, help="n (even)")
    args = parser.parse_args()

    # import modules
    v123_path = os.path.join(HERE, "v_1_2_3.py")
    v4_path = os.path.join(HERE, "v_4.py")
    try:
        module_v123 = import_module(v123_path)
    except Exception as e:
        print(f"[ERROR] Could not import v_1_2_3.py: {e}", file=sys.stderr)
        traceback.print_exc()
        module_v123 = None
    try:
        module_v4 = import_module(v4_path)
    except Exception as e:
        print(f"[ERROR] Could not import v_4.py: {e}", file=sys.stderr)
        traceback.print_exc()
        module_v4 = None

    # Batch mode: no version specified
    if args.version is None:
        print("[INFO] No version specified -> running batch for v_1_2_3 and v_4")
        if module_v123 is not None:
            run_v123_batch(module_v123)
        else:
            print("[WARN] module_v123 not available: skipping v_1_2_3 batch")
        if module_v4 is not None:
            run_v4_batch(module_v4)
        else:
            print("[WARN] module_v4 not available: skipping v_4 batch")
        print("[INFO] Batch finished.")
        return

    # Single-version mode: user passed --version and --instance (n)
    ver = args.version.strip().lower()
    n = args.n
    if n is None:
        print("[ERROR] When specifying --version you must also specify --instance (n).", file=sys.stderr)
        sys.exit(2)

    # Normalise version tokens: accept 'v1' -> 'v1' (we map to v_1 behavior), 'v3' -> i<j, 'v4' -> pre
    if ver in ("v1", "base", "v_1"):
        run_v1_single(n, module_v123)
    elif ver in ("v2",):
        run_v2_single(n, module_v123)
    elif ver in ("v3", "i<j", "v_3"):
        run_v3_single(n, module_v123)
    elif ver in ("v4", "pre", "preprocessing"):
        run_v4_single(n, module_v4)
    elif ver in ("v5",):
        run_v5_single(n, module_v123)
    elif ver in ("v6",):
        # v6 needs both modules (v_1_2_3 and v_4)
        run_v6_single(n, module_v123, module_v4)
    else:
        print(f"[ERROR] Unknown version token: {args.version}", file=sys.stderr)
        sys.exit(4)

if __name__ == "__main__":
    main()
