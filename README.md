# CDMOproject
Project for the Combinatorial Decision Making &amp; Optimization course of the MAster's Degree in Artificial Intelligence of UniBo

# Docker usage (quick guide)

This README explains how to build and run the project image using **only Docker CLI**. It documents the available flags that the container entrypoint accepts, shows concrete examples, and lists the available versions and which version token to pass when you want to run a specific experiment.

All commands assume you run them from the project root where the `Dockerfile` and the `source/` directory live.

---

## Build the Docker image

Build the image once (from project root):

```bash
docker build -t sts-container .
```

---

## Mount host folders into the container

You should mount your working `source/` and `res/` directories into the container so the container uses your code and writes outputs back to the host:

```bash
# Unix / macOS (bash / zsh)
-v "$(pwd)/source:/CDMO/source" -v "$(pwd)/res:/CDMO/res"
```

On PowerShell use `${PWD}` instead of `$(pwd)`.

---

## Entrypoint behavior & supported flags

The container entrypoint accepts two styles of invocation:

1. **No arguments (batch mode)**
   If you run the container **without passing any arguments**, the entrypoint will sequentially run every approach:
   `CP`, `SMT`, `MIP` — invoking `python /CDMO/source/<APPROACH>/main.py` for each approach **with default parameters**.

2. **Single-approach mode (positional or flag style)**
   If you pass arguments, the entrypoint will run a single approach only.

   * **Positional form**:

     ```bash
     docker run --rm -v "$(pwd)/source:/CDMO/source" -v "$(pwd)/res:/CDMO/res" \
       sts-container MIP 8 v1
     ```

     This runs `python /CDMO/source/MIP/main.py --instance 8 --version v1`.

   * **Flag form**:

     ```bash
     docker run --rm -v "$(pwd)/source:/CDMO/source" -v "$(pwd)/res:/CDMO/res" \
       sts-container -- --approach MIP --n 8 --version v1
     ```

     This runs the same `main.py` and forwards `--n 8 --version v1`.

### Supported flags (forwarded by the entrypoint)

* `--approach <APPROACH>` — one of `CP`, `SMT`, `MIP` (case-insensitive).
* `--n` or `--instance <int>` — instance size (even integer).
* `--version <str>` — version token (e.g. `v1`, `v3`, `v4`).
* `-h`, `--help` — show help (entrypoint prints usage).


---

## Examples

### 1) Run everything (batch mode)

Runs all four approaches (`CP`, `SMT`, `MIP`) sequentially, no parameters:

```bash
docker run --rm \
  -v "$(pwd)/source:/CDMO/source" \
  -v "$(pwd)/res:/CDMO/res" \
  sts-container
```

### 2) Run only MIP with positional args (n=8, version=v1)

Positional style:

```bash
docker run --rm \
  -v "$(pwd)/source:/CDMO/source" \
  -v "$(pwd)/res:/CDMO/res" \
  sts-container MIP 8 v1
```

This calls `/CDMO/source/MIP/main.py --instance 8 --version v1`.

### 3) Run only MIP with flag args (identical behavior)

Flag style (note the `--` after the image):

```bash
docker run --rm \
  -v "$(pwd)/source:/CDMO/source" \
  -v "$(pwd)/res:/CDMO/res" \
  sts-container -- --approach MIP --n 8 --version v1
```

### 4) Enter an interactive shell in the container (dev debugging)

If you want a shell inside the image (mounting your source/res):

```bash
docker run --rm -it \
  -v "$(pwd)/source:/CDMO/source" \
  -v "$(pwd)/res:/CDMO/res" \
  sts-container /bin/bash
```

Then you can run commands manually inside the container, e.g.:

```bash
python /CDMO/source/MIP/main.py --instance 8 --version v1
```

---

## CP: available versions

The following list serves as index to know which version runs a particular model (all the cited model are described in the report).

| version  | meaning / which implementation is used                                                                                                                                           |
| --------------------- | ---------------------------------------------------------------------------------- |
| `v1`                  | Will run the round_robin_model with HAP_v1_model optimization, with 'chuffed' solver |
| `v2`                  | Will run the constraint_v2_model with HAP_v1_model optimization, with 'chuffed' solver |
| `v3`                  | Will run the constraint_v2_model non optimized, with 'gecode' solver |
| `v4`                  | Will run the constraint_v1_model non optimized, with 'gecode' solver |
| `v5`                  | Will run the naive_model non optimized, with 'gecode' solver |

---

## SMT: available versions
The following list serves as index to know which version runs a particular model (all the cited model are described in the report).

| version  | meaning / which implementation is used                                                                                                                                           |
| --------------------- | ---------------------------------------------------------------------------------- |
| `v1`                  | Will run the channeled model with the z3 solver |
| `v2`                  | Will run the preprocessed model with the z3 solver |
| `v3`                  | Will run the channeled model with the cvc5 solver |
| `v4`                  | Will run the preprocessed model with the cvc5 solver |
| `v5`                  | Will run the channeled model with the optimathsat solver |
| `v6`                  | Will run the preprocessed model with the optimathsat solver |

  **Single-version mode** 
* When just `--version` is passed, that version is run with all the even instances from 4 to 18;
* When just `--n` is passed, that instance is run with all the six versions;
* When both `--version` and `--n` are passed, then the chosen instance on the chosen version is performed;
* When none of the two is passed, all the feasible instances will be run, so the one which on the report timeout, will not run.

---

## MIP: available versions 

| version token to pass | meaning / which implementation is used                                                                                                                                                    |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `v1`                  | the best CBC and GLPK **base** — **feasible** model                                                       |
| `v2`                  | Useful to verify the behaviour of CBC `i!=j` and compare it to `v1`/`v3`.         |
| `v3`                  | the best CBC and GLPK **i\<j**-**balanced**.              |
| `v4`                  | the best CBC and GLPK **pre** - **feasible/balanced**.                                                                             |
| `v5`                  | **seed-sensitivity sweep** — runs the same CBC base-feasible case over many seeds (0, 1234567, 26, 42, 262626, 424242, 878641, 5656565). Usefull to see how changing seed, changes the the performance of the same model.          |
| `v6`                  | **GLPK robustness & cuts** — multiple GLPK combos (seeds, cuts on/off, base vs i\<j) usefull to check the performance of GLPK |

#### Where results are written

* **Batch mode (no args)**: the MIP batch writes files into:

  ```
  /CDMO/res/MIP/{nn}.json
  ```

* **Single-version mode** (when you pass `--version` and `--instance`) the script writes to:

  ```
  /CDMO/res/additional_tests/{n}.json
  ```
