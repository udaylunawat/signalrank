import pandas as pd

# Load the CSV
df = pd.read_csv("outputs/ranked_jobs.csv")

# Sort by final_score descending and select top 5
top5 = df.sort_values("final_score", ascending=False) #.head(5)

# Extract job descriptions
descriptions = top5[["title", "company", "final_score", "description", "max_yoe"]] #.head(5)

# Print or save the descriptions
for idx, row in descriptions.iterrows():
    print(f"Title: {row['title']}")
    print(f"Company: {row['company']}")
    print(f"YOE: {row['max_yoe']}")
    print(f"Score: {row['final_score']}")
    # print("Description:")
    # print(row['description'])
    print("="*80)