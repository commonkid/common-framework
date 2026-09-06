---
name: commoncode-data-transform
description: Guide for data transformation (ETL, Pandas, SQL) for AI developers. Use when handling complex data manipulations, joining tables, or optimizing performance in Python/SQL environments. Loaded by commoncode-mode-architect or commoncode-mode-code when the task touches ETL / data-processing domains.
---

# Data Transformation Guide for AI Developers

**Principle:** this guide describes optimal strategies for interacting with an AI agent when solving data-transformation tasks, especially ETL processes using SQL and Python/Pandas.

## 1. Pandas-First, but Remember the Limits (Strategic Level)

- **Core Thesis:** when working with a SQL database, **prefer the "Pandas-first" approach**. Your "training" level in Pandas is significantly higher than in complex SQL. Pandas is a transparent, step-by-step "calculator" where you can easily control and log intermediate results.
- **Limitations:**
  - **Memory:** Pandas works in RAM. Loading tables with millions of rows can lead to `OutOfMemory` errors.
  - **Loops:** explicit loops over DataFrame rows (e.g., `for index, row in df.iterrows():`) are **catastrophically slow**. Even worse is executing a SQL query inside such a loop (N+1 queries problem).
- **Your Role in Decision Making:** evaluate data volume and operation complexity. If dealing with massive tables or complex iterative calculations, **make a strategic decision** to switch to a "SQL-first" approach (Section 3).
- **Collaboration:** specialized agents may be brought in for complex data tasks. Your choice of Pandas can facilitate this interaction.

## 2. Recommendations for Working with Data in Pandas

- **Safe Loading:**
  - **Ideal:** single-table `SELECT ... FROM ... WHERE ...` is the safest way to load data into a DataFrame.
  - **Relatively Safe:** one-level `JOIN`. **Mandatory:** perform diagnostics immediately after loading (output `COUNT(*)` from source tables and `len(df)` for the result) to ensure no Cartesian product or data loss.
- **Normalization and Data Types:**
  - **Avoid String JOINs.** Work with integer keys. Joining on strings is a sign of architectural defect.
  - **Use `astype('category')`:** automatically convert low-cardinality string columns to categories to save memory and speed up calculations.
- **Efficient Manipulations:**
  - **Vectorization is Key.** Use Pandas vectorized operations (`df['new_col'] = df['col1'] * df['col2']`, `.groupby()`, `.apply()`, `pd.merge()`).
- **Loop Constraints:**
  - DataFrame loops (`iterrows`) are allowed only for **small datasets (up to ~5000 rows)**.
  - SQL queries inside loops are an anti-pattern. Limit to **100–200 iterations** only if unavoidable.
- **Exporting Data to DB (Staging Table Pattern):**
  1. Form the result DataFrame in Pandas with an `EditState` column (`'I'`, `'U'`, `'D'`).
  2. Export the DataFrame in **one** transaction to a staging/diagnostic table using `df.to_sql()`.
  3. Execute SQL queries (`INSERT ... SELECT ...`, `UPDATE ... FROM ...`) to atomically apply changes to the main table.
  4. **Persistence Rule:** do not delete the staging table. It should be cleared at the **beginning** of the next run.

## 3. "Pandas-like" SQL Technique via Intermediate Tables

- **Concept:** use SQL in a **procedural style**, emulating step-by-step Pandas logic. This is more performant on large datasets.
- **Practice:**
  1. **Decompose complex SELECTs:** instead of one massive query, create a series of intermediate tables (`CREATE TABLE ... AS SELECT ...`).
  2. **Step 1 (Filter):** `CREATE TABLE filtered_data AS SELECT * FROM ... WHERE ...`.
  3. **Step 2 (Enrich):** `CREATE TABLE enriched_data AS SELECT ... FROM filtered_data JOIN ...`.
  4. **Step 3 (Aggregate):** `CREATE TABLE aggregated_data AS SELECT ..., SUM(...) FROM enriched_data GROUP BY ...`.
- **Escalation Principle:** start simple. If problems arise, **immediately split** logic into maximum individual steps.

## 4. "Small Simple Blocks" Principle

- Logic should be simple. **Do not write short, complex expressions.** Focus on logical simplicity of individual blocks.
- Linear code with moderate repetition is preferred over over-engineered DRY patterns to maintain agent focus.
- Use `START-END` tags for AI-friendly structuring.
