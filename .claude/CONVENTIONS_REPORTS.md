# Report Conventions

When creating or editing markdown reports in the `reports/` directory, follow these conventions. See existing reports in `reports/` for examples.

## Front matter

- **Title**: `# Descriptive Title` as the first line.
- **Byline**: `#### Maria Silva, {Month Year}` immediately after the title (use `###` for standalone reports outside EIP subdirectories).
- **Opening paragraph**: 1-3 sentences situating the report in the series — link to prior reports it builds on, state what this report adds, and name the specific EIP(s) it informs.
- **Key findings / TLDR**: A bulleted summary of 3-5 takeaways right after the intro, before the body. Use **bold lead-ins** for each bullet. This lets readers get the main results without reading the full report.

## Structure

Reports follow a consistent section flow:

1. **Background / Context** — Prior work, motivation, and how this report connects to the series.
2. **Methodology** — Model description, parameter tables, data sources, and estimation approach.
3. **Results** — Organized into subsections by metric or dimension (e.g., "Impact on state growth", "Impact on throughput"). Each subsection presents figures, tables, and interpretation together.
4. **Conclusions / Discussion / Next Steps** — Summarize findings with numbered takeaways and outline follow-up work.

Use `##` for top-level sections and `###` for subsections within them.

## Writing style

- **Tone**: Technical but accessible. Write in first-person plural ("we find", "our analysis", "we recommend").
- **Descriptive, not prescriptive**: Document what the data shows rather than making strong causal claims. Use language like "consistent with", "suggests that", "is associated with" rather than "proves" or "causes".
- **Acknowledge limitations**: Explicitly note when results depend on assumptions, when data is observational, or when uncertainty is high (e.g., "we do not claim causal effects", "this is not a controlled experiment").
- **Interpretation blocks**: After presenting figures or tables, include a paragraph or bullet list labeled **Key findings:**, **Key observations:**, or **Interpretation:** that explains what the results mean. Do not leave figures or tables without commentary.
- **Quantify claims**: Always include specific numbers (e.g., "median base fee drops ~89.6%", "throughput gains of 1.3x-1.4x") rather than vague qualifiers.

## Figures and tables

- **Figures**: Store in `reports/figures/{report_name}/` subdirectories. Reference with markdown image syntax: `![description](./figures/{report_name}/filename.png)` for local references or full GitHub raw URLs for external linking.
- **Tables**: Use markdown tables for parameter definitions, summary statistics, and result comparisons. Always include column headers and right-align numeric columns with `---:`.
- **Parameter tables**: When presenting a model, include a table with columns: Parameter, Value, Description. This makes the analysis reproducible.
- **Result tables**: Include units in column headers (e.g., "Mean (gwei)", "Max state growth (GiB/yr)").

## Math

- Use LaTeX math extensively for model definitions and derivations.
- Inline math with `$...$` for variables and short expressions (e.g., `$\varepsilon_s \approx 0.3$–$0.6$`).
- Display math with `$$...$$` for equations and derivations.
- Number important equations with `\tag{N}` when they are referenced later in the text.
- Use standard notation consistently across reports: $\varepsilon_s$ for state elasticity, $\varepsilon_b$ for burst elasticity, $m$ for repricing multiplier, $n$ for gas limit multiplier, $s$ for state share, $r$ for base fee ratio, $b^0$ for baseline base fee, $G^0$ for current gas limit, $S^0$ for current state growth.

## Cross-references and reproducibility

- **Link to prior reports**: When building on previous analysis, link to the published ethresear.ch post or the report markdown file in the repo.
- **Link to notebooks**: Include a link to the notebook that reproduces the analysis (e.g., "The analysis can be reproduced by running this [notebook](link)").
- **Link to data sources**: Reference external data sources (e.g., Xatu dataset) with links.
- **Link to EIPs**: Reference EIPs with links to `eips.ethereum.org` (e.g., `[EIP-8037](https://eips.ethereum.org/EIPS/eip-8037)`).
