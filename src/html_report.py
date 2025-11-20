"""
HTML report generation for PS3/BS3 analysis results.
"""

from typing import Dict, Any
from pathlib import Path


def generate_html_report(result: Dict[str, Any], output_path: str) -> None:
    """
    Generate an HTML report from analysis results.

    Parameters
    ----------
    result : dict
        Dictionary containing analysis results with keys:
        - variant_info
        - candidate_papers
        - functional_papers
        - experiments
        - assessment
    output_path : str
        Path where the HTML file will be saved
    """
    variant_info = result["variant_info"]
    candidate_papers = result["candidate_papers"]
    functional_papers = result["functional_papers"]
    experiments = result["experiments"]
    assessment = result["assessment"]

    # Build HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PS3/BS3 Analysis Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 30px;
            border-left: 4px solid #667eea;
            padding-left: 20px;
        }}
        .section h2 {{
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 15px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .info-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #e9ecef;
        }}
        .info-card .label {{
            font-weight: bold;
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
        }}
        .info-card .value {{
            font-size: 1.1em;
            margin-top: 5px;
            word-break: break-word;
        }}
        .assessment-box {{
            background: #f0f4ff;
            border: 2px solid #667eea;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .assessment-decision {{
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .ps3 {{
            color: #d32f2f;
        }}
        .bs3 {{
            color: #388e3c;
        }}
        .none {{
            color: #f57c00;
        }}
        .narrative {{
            font-size: 1.05em;
            line-height: 1.8;
            margin-top: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #f0f4ff;
            color: #667eea;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #667eea;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            margin-right: 5px;
        }}
        .badge-paper {{
            background: #e3f2fd;
            color: #1565c0;
        }}
        .badge-experiment {{
            background: #f3e5f5;
            color: #6a1b9a;
        }}
        .badge-supporting {{
            background: #c8e6c9;
            color: #2e7d32;
        }}
        .badge-ambiguous {{
            background: #ffe0b2;
            color: #e65100;
        }}
        .experiment-item {{
            background: #fafafa;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
            border-left: 4px solid #764ba2;
        }}
        .experiment-item .key {{
            font-weight: 600;
            color: #764ba2;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            border-top: 1px solid #e9ecef;
            color: #666;
            font-size: 0.9em;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .stat-box {{
            flex: 1;
            min-width: 150px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PS3/BS3 Functional Evidence Analysis</h1>
            <p>ACMG Variant Classification Report</p>
        </div>

        <div class="content">
            <!-- Variant Information Section -->
            <div class="section">
                <h2>1. Variant Information</h2>
                <div class="info-grid">
                    <div class="info-card">
                        <div class="label">Genomic Coordinates</div>
                        <div class="value">{variant_info['chrom']}:{variant_info['pos']}</div>
                    </div>
                    <div class="info-card">
                        <div class="label">Alleles</div>
                        <div class="value">{variant_info['ref']} → {variant_info['alt']}</div>
                    </div>
                    {f'<div class="info-card"><div class="label">Gene Symbol</div><div class="value">{variant_info.get("gene_symbol", "N/A")}</div></div>' if variant_info.get('gene_symbol') else ''}
                    {f'<div class="info-card"><div class="label">rsID</div><div class="value">{variant_info.get("rsid", "N/A")}</div></div>' if variant_info.get('rsid') else ''}
                    {f'<div class="info-card"><div class="label">HGVSc</div><div class="value">{variant_info.get("hgvsc", "N/A")}</div></div>' if variant_info.get('hgvsc') else ''}
                    {f'<div class="info-card"><div class="label">HGVSp</div><div class="value">{variant_info.get("hgvsp", "N/A")}</div></div>' if variant_info.get('hgvsp') else ''}
                </div>
            </div>

            <!-- Literature Summary Section -->
            <div class="section">
                <h2>2. Literature Summary</h2>
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{len(candidate_papers)}</div>
                        <div class="stat-label">Candidate Papers</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{len(functional_papers)}</div>
                        <div class="stat-label">Functional Papers</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{len(experiments)}</div>
                        <div class="stat-label">Experiments</div>
                    </div>
                </div>
                {_generate_papers_table(functional_papers) if functional_papers else '<p>No functional papers identified.</p>'}
            </div>

            <!-- Experiments Section -->
            <div class="section">
                <h2>3. Functional Experiments</h2>
                {_generate_experiments_html(experiments) if experiments else '<p>No experiments extracted.</p>'}
            </div>

            <!-- Assessment Section -->
            <div class="section">
                <h2>4. ACMG Assessment</h2>
                <div class="assessment-box">
                    <div class="assessment-decision">
                        Decision: 
                        <span class="{'ps3' if assessment['decision'] == 'PS3' else 'bs3' if assessment['decision'] == 'BS3' else 'none'}">
                            {assessment['decision']}
                        </span>
                    </div>
                    {f'<div class="stat-label">Strength: {assessment.get("strength", "N/A").upper()}</div>' if assessment.get('strength') else ''}
                    <div class="narrative">
                        {assessment['narrative']}
                    </div>
                    {f'<p style="margin-top: 15px; font-size: 0.9em;"><strong>Key PMIDs:</strong> {", ".join(assessment.get("key_pmids", []))}</p>' if assessment.get('key_pmids') else ''}
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Report generated by PS3/BS3 Analysis Pipeline</p>
            <p>For more information, visit: <a href="https://github.com/AliSaadatV/AcmGENTIC" style="color: #667eea;">AcmGENTIC on GitHub</a></p>
        </div>
    </div>
</body>
</html>"""

    # Write HTML to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_content)


def _generate_papers_table(functional_papers: list) -> str:
    """Generate HTML table of functional papers."""
    if not functional_papers:
        return "<p>No functional papers identified.</p>"

    rows = ""
    for paper in functional_papers:
        rows += f"""
        <tr>
            <td><span class="badge badge-paper">{paper['pmid']}</span></td>
            <td>{paper['title'][:80]}...</td>
            <td>{paper['justification'][:60]}...</td>
        </tr>
        """

    return f"""
    <table>
        <thead>
            <tr>
                <th>PMID</th>
                <th>Title</th>
                <th>Justification</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    """


def _generate_experiments_html(experiments: list) -> str:
    """Generate HTML for experiments."""
    if not experiments:
        return "<p>No experiments extracted.</p>"

    html = ""
    for i, exp in enumerate(experiments, 1):
        evaluation_class = "badge-supporting" if exp['evaluation'] == "supports_pathogenic" else "badge-ambiguous"
        html += f"""
        <div class="experiment-item">
            <div><span class="key">Experiment {i} (PMID {exp['pmid']})</span> <span class="badge {evaluation_class}">{exp['evaluation']}</span></div>
            <p><span class="key">Assay Type:</span> {exp['assay_type']}</p>
            <p><span class="key">System:</span> {exp['system']}</p>
            <p><span class="key">Readout:</span> {exp['readout']}</p>
            <p><span class="key">Effect Direction:</span> {exp['effect_direction']}</p>
            <p><span class="key">Magnitude & Stats:</span> {exp['magnitude_stats']}</p>
            <p><span class="key">Controls & Quality:</span> {exp['controls_validity']}</p>
            <p><span class="key">Authors' Conclusion:</span> {exp['authors_conclusion']}</p>
        </div>
        """

    return html
