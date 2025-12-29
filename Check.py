import pandas as pd
with pd.option_context('display.max_rows', None):
    data = pd.read_csv('contour_comparison_results_P0728.csv')
    print(data)