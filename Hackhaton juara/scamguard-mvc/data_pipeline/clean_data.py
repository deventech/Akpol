"""Pembersihan data hasil scraping: hapus duplikat, tangani nilai hilang (proposal bab 2.3).
Pakai: python data_pipeline/clean_data.py data_pipeline/raw/data.jsonl data_pipeline/processed/clean.csv
"""
import sys
import pandas as pd


def clean(src: str, dst: str) -> None:
    df = pd.read_json(src, lines=True) if src.endswith(".jsonl") else pd.read_csv(src)
    df = df.drop_duplicates(subset="url").dropna(subset=["url"])
    if "label" in df:
        df["label"] = df["label"].fillna("unknown")  # phishing / legitimate / gambling / unknown
    df.to_csv(dst, index=False)
    print(f"{len(df)} baris tersimpan di {dst}")


if __name__ == "__main__":
    clean(sys.argv[1], sys.argv[2])
