import pandas as pd
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

FILE_PATH = r'contour_comparison_results_P0728_v6.xlsx'  # Update path if needed
COLUMN    = 'pNumber'

# ============================================================================
# COUNT UNIQUE VALUES
# ============================================================================

path = Path(FILE_PATH)
if not path.exists():
    print(f"Error: File not found: {path.absolute()}")
else:
    df = pd.read_excel(path) if path.suffix == '.xlsx' else pd.read_csv(path)

    if COLUMN not in df.columns:
        print(f"Error: Column '{COLUMN}' not found.")
        print(f"Available columns: {list(df.columns)}")
    else:
        # ── Overall unique patient count ─────────────────────────────────────
        unique_vals = df[COLUMN].dropna().unique()
        n_unique    = len(unique_vals)

        print(f"File             : {path.name}")
        print(f"Total rows       : {len(df)}")
        print(f"Unique {COLUMN}s : {n_unique}")

        # ── Filter by ChainStatus ────────────────────────────────────────────
        KEEP_STATUSES = [
            'No approved RTPLANs',
            'Limbus AI RTSTRUCT not found (no verified match)',
        ]

        if 'ChainStatus' not in df.columns:
            print("\nWarning: Column 'ChainStatus' not found – skipping status filter.")
        else:
            df_filtered = df[df['ChainStatus'].isin(KEEP_STATUSES)]
            unique_filtered = df_filtered[COLUMN].dropna().unique()

            print()
            print(f"── Filtered: ChainStatus in {KEEP_STATUSES} ──")
            print(f"Matching rows          : {len(df_filtered)}")
            print(f"Unique {COLUMN}s       : {len(unique_filtered)}")
            print()
            print(f"{'Patient':<30} {'ChainStatus'}")
            print("─" * 80)
            for val in sorted(unique_filtered):
                statuses = df_filtered.loc[df_filtered[COLUMN] == val, 'ChainStatus'].unique()
                for status in statuses:
                    print(f"  {str(val):<28} {status}")
