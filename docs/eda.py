import pandas as pd

# Load the CSV
df = pd.read_csv('/home/ubuntu/dev/lfx/krkn-hub/docs/edge-cases.csv')

# Show basic info
print("Shape:", df.shape)
print("\nColumns:", df.columns.tolist())
print("\nFirst 5 rows:\n", df.head())

# Count unique values in each column
print("\nUnique values per column:")
for col in df.columns:
    print(f"{col}: {df[col].nunique()}")

# Value counts for 'label' and 'type'
print("\nLabel distribution:\n", df['label'].value_counts())
print("\nType distribution:\n", df['type'].value_counts())

# Check for missing values
print("\nMissing values:\n", df.isnull().sum())