"""
Create clean summary CSV files from benchmark results.
"""
import pandas as pd

# Read results
df = pd.read_csv('all_benchmarks_results.csv')

# Separate SB and GT
sb_df = df[df['algorithm'] == 'SB'].copy()
gt_df = df[df['algorithm'] == 'GT'].copy()

# Clean up columns
sb_df = sb_df[['instance', 'size', 'bks', 'makespan', 'gap_pct', 'optimal', 'time_s']]
gt_df = gt_df[['instance', 'size', 'bks', 'rule', 'makespan', 'gap_pct', 'optimal', 'time_s']]

# Rename columns for clarity
sb_df.columns = ['Instance', 'Size', 'BKS', 'Makespan', 'Gap%', 'Optimal', 'Time(s)']
gt_df.columns = ['Instance', 'Size', 'BKS', 'Rule', 'Makespan', 'Gap%', 'Optimal', 'Time(s)']

# Round numbers
sb_df['Gap%'] = sb_df['Gap%'].round(2)
sb_df['Time(s)'] = sb_df['Time(s)'].round(3)
gt_df['Gap%'] = gt_df['Gap%'].round(2)
gt_df['Time(s)'] = gt_df['Time(s)'].round(4)

# Save separate files
sb_df.to_csv('results_sb.csv', index=False)
gt_df.to_csv('results_gt.csv', index=False)

print("✅ Created results_sb.csv")
print(f"   - {len(sb_df)} instances")
print(f"   - {sb_df['Optimal'].sum()} optimal")
print(f"   - {sb_df['Gap%'].mean():.2f}% avg gap")
print()
print("✅ Created results_gt.csv")
print(f"   - {len(gt_df)} instances")
print(f"   - {gt_df['Optimal'].sum()} optimal")
print(f"   - {gt_df['Gap%'].mean():.2f}% avg gap")
print()

# Create combined comparison
comparison = pd.merge(
    sb_df[['Instance', 'Size', 'BKS', 'Makespan', 'Gap%', 'Optimal', 'Time(s)']],
    gt_df[['Instance', 'Makespan', 'Gap%', 'Time(s)']],
    on='Instance',
    suffixes=('_SB', '_GT')
)

# Add winner column
comparison['Winner'] = comparison.apply(
    lambda row: 'SB' if row['Makespan_SB'] < row['Makespan_GT'] 
    else ('GT' if row['Makespan_GT'] < row['Makespan_SB'] else 'Tie'),
    axis=1
)

comparison.to_csv('results_comparison.csv', index=False)
print("✅ Created results_comparison.csv")
print(f"   - SB wins: {(comparison['Winner'] == 'SB').sum()}")
print(f"   - GT wins: {(comparison['Winner'] == 'GT').sum()}")
print(f"   - Ties: {(comparison['Winner'] == 'Tie').sum()}")
