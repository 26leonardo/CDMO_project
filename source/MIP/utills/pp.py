import os
import json
import pandas as pd
import re

def collect_results(json_dir: str, output_csv: str = "summary.csv"):
    rows = []
    all_keys = set()

    # Ordina i file json in base al numero prima di .json
    def extract_num(fname):
        match = re.match(r"(\d+)\.json$", fname)
        return int(match.group(1)) if match else float("inf")

    file_list = sorted(
        [f for f in os.listdir(json_dir) if f.endswith(".json")],
        key=extract_num
    )

    # Carico tutti i file json della directory
    for fname in file_list:
        fpath = os.path.join(json_dir, fname)
        with open(fpath, "r") as f:
            data = json.load(f)

        row = {"file": fname}
        for key, vals in data.items():
            time = vals.get("time", None)
            obj = vals.get("obj", None)
            row[key] = f"{time}={obj}"
            all_keys.add(key)

        rows.append(row)

    # Creo dataframe con tutte le colonne possibili
    df = pd.DataFrame(rows)
    df = df.set_index("file")
    df = df.reindex(columns=sorted(all_keys))

    # Salvo su CSV
    df.to_csv(output_csv)
    print(f"Risultati salvati in {output_csv}")
    return df


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python collect_results.py <json_directory>")
    else:
        directory = sys.argv[1]
        df = collect_results(directory)
        print(df)
