"""
HTML and PDF report generation for PS3/BS3 analysis results.
"""

from typing import Dict, Any, Optional
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
            background: #f0fdfa;
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
            background: #0d9488;
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
            border-left: 4px solid #0d9488;
            padding-left: 20px;
        }}
        .section h2 {{
            font-size: 1.8em;
            color: #0d9488;
            margin-bottom: 15px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .info-card {{
            background: #f0fdfa;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #99f6e4;
        }}
        .info-card .label {{
            font-weight: bold;
            color: #0d9488;
            font-size: 0.9em;
            text-transform: uppercase;
        }}
        .info-card .value {{
            font-size: 1.1em;
            margin-top: 5px;
            word-break: break-word;
        }}
        .assessment-box {{
            background: #f0fdfa;
            border: 2px solid #0d9488;
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
            background: #f0fdfa;
            color: #0d9488;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #0d9488;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
        }}
        tr:hover {{
            background: #f0fdfa;
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
            background: #ccfbf1;
            color: #0d9488;
        }}
        .badge-experiment {{
            background: #d1fae5;
            color: #047857;
        }}
        .badge-supporting {{
            background: #c8e6c9;
            color: #2e7d32;
        }}
        .badge-ambiguous {{
            background: #ffe0b2;
            color: #e65100;
        }}
        .badge-pathogenic {{
            background: #ffcdd2;
            color: #c62828;
        }}
        .badge-benign {{
            background: #fff9c4;
            color: #f57f17;
        }}
        .experiment-item {{
            background: #fafafa;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
            border-left: 4px solid #14b8a6;
        }}
        .experiment-item .key {{
            font-weight: 600;
            color: #0f766e;
        }}
        .footer {{
            background: #f0fdfa;
            padding: 20px;
            text-align: center;
            border-top: 1px solid #99f6e4;
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
            background: #f0fdfa;
            padding: 20px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #0d9488;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PS3/BS3 Functional Evidence Analysis</h1>
            <p>ACMG/AMP Variant Classification Report (PS3/BS3 criteria) </p>
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
            </div>

            <!-- Experiments Section -->
            <div class="section">
                <h2>3. Functional Experiments</h2>
                {_generate_experiments_html(experiments, functional_papers) if experiments else '<p>No experiments extracted.</p>'}
            </div>

            <!-- Assessment Section -->
            <div class="section">
                <h2>4. ACMG/AMP Assessment</h2>
                <div class="assessment-box">
                    <div class="assessment-decision">
                        Decision: 
                        <span class="{'ps3' if assessment['decision'] == 'PS3' else 'bs3' if assessment['decision'] == 'BS3' else 'none'}">
                            {assessment['decision']}
                        </span>
                    </div>
                    {f'<div class="stat-label">Strength: {assessment.get("strength", "N/A").upper()}</div>' if assessment.get('strength') else ''}
                    {f'<div class="stat-label">Confidence: {assessment.get("confidence", "N/A")}</div>' if assessment.get('confidence') else ''}
                    <div class="narrative">
                        {assessment['narrative']}
                    </div>
                    {f'<p style="margin-top: 15px; font-size: 0.9em;"><strong>Key PMIDs:</strong> {", ".join(assessment.get("key_pmids", []))}</p>' if assessment.get('key_pmids') else ''}
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Report generated by PS3/BS3 Analysis Pipeline</p>
            <p>For more information, visit: <a href="https://github.com/AliSaadatV/AcmGENTIC" style="color: #0d9488;">AcmGENTIC on GitHub</a></p>
        </div>
    </div>
</body>
</html>"""

    # Write HTML to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_content)


def _generate_experiments_html(experiments: list, functional_papers: list) -> str:
    """Generate HTML for experiments with paper title and justification."""
    if not experiments:
        return "<p>No experiments extracted.</p>"

    # Create lookup dictionary for paper info by PMID
    paper_lookup = {
        p['pmid']: {'title': p.get('title') or 'N/A', 'justification': p.get('justification') or 'N/A'}
        for p in functional_papers
    } if functional_papers else {}

    html = ""
    for i, exp in enumerate(experiments, 1):
        # Determine evaluation class for badge styling
        eval_value = exp.get('evaluation', 'ambiguous')
        if eval_value == "supports_pathogenic":
            evaluation_class = "badge-pathogenic"
        elif eval_value == "supports_benign":
            evaluation_class = "badge-benign"
        else:
            evaluation_class = "badge-ambiguous"
        
        # Get paper info from lookup
        pmid = exp['pmid']
        paper_info = paper_lookup.get(pmid, {'title': 'N/A', 'justification': 'N/A'})
        title = paper_info['title']
        justification = paper_info['justification']
        
        # Get values with fallbacks for empty strings
        assay_type = exp.get('assay_type') or "N/A"
        system = exp.get('system') or "N/A"
        readout = exp.get('readout') or "N/A"
        effect_direction = exp.get('effect_direction') or "N/A"
        magnitude_stats = exp.get('magnitude_stats') or "N/A"
        controls_validity = exp.get('controls_validity') or "N/A"
        authors_conclusion = exp.get('authors_conclusion') or "N/A"
        
        html += f"""
        <div class="experiment-item" style="word-wrap: break-word; overflow-wrap: break-word;">
            <div style="margin-bottom: 10px;"><span class="key">Experiment {i} (Title: {title} PMID: {pmid})</span> <span class="badge {evaluation_class}">{eval_value}</span></div>
            <p style="margin-bottom: 8px;"><span class="key">Justification of Paper Inclusion:</span> {justification}</p>
            <p style="margin-bottom: 8px;"><span class="key">Assay Type:</span> {assay_type}</p>
            <p style="margin-bottom: 8px;"><span class="key">System:</span> {system}</p>
            <p style="margin-bottom: 8px;"><span class="key">Readout:</span> {readout}</p>
            <p style="margin-bottom: 8px;"><span class="key">Effect Direction:</span> {effect_direction}</p>
            <p style="margin-bottom: 8px;"><span class="key">Magnitude & Stats:</span> {magnitude_stats}</p>
            <p style="margin-bottom: 8px;"><span class="key">Controls & Quality:</span> {controls_validity}</p>
            <p style="margin-bottom: 0;"><span class="key">Authors' Conclusion:</span> {authors_conclusion}</p>
        </div>
        """

    return html


def generate_pdf_report(result: Dict[str, Any], output_path: str) -> None:
    """
    Generate a PDF report from analysis results using WeasyPrint.

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
        Path where the PDF file will be saved
        
    Raises
    ------
    ImportError
        If WeasyPrint is not installed
    """
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        raise ImportError(
            "WeasyPrint is required for PDF generation. "
            "Install it with: pip install weasyprint\n"
            "Note: WeasyPrint requires system libraries (cairo, pango). "
            "See https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation"
        )
    
    # First generate HTML content (reuse existing function)
    import tempfile
    import os
    
    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
        # Generate HTML to temp file
        generate_html_report(result, tmp.name)
        tmp_path = tmp.name
    
    try:
        # Read the HTML content
        with open(tmp_path, 'r') as f:
            html_content = f.read()
        
        # Add PDF-specific styles
        pdf_css = CSS(string="""
            @page {
                size: A4;
                margin: 1.5cm;
            }
            body {
                background: white !important;
                padding: 0 !important;
            }
            .container {
                box-shadow: none !important;
            }
            .header {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            table {
                page-break-inside: avoid;
            }
            .experiment-item {
                page-break-inside: avoid;
            }
            .section {
                page-break-inside: avoid;
            }
        """)
        
        # Generate PDF
        html = HTML(string=html_content)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        html.write_pdf(str(output_file), stylesheets=[pdf_css])
        
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def generate_reports(
    result: Dict[str, Any],
    output_dir: str,
    variant_label: str,
    formats: str = "both",
) -> Dict[str, str]:
    """
    Generate reports in specified formats.

    Parameters
    ----------
    result : dict
        Dictionary containing analysis results
    output_dir : str
        Directory where reports will be saved
    variant_label : str
        Label for the variant (used in filename)
    formats : str
        Output format(s): 'html', 'pdf', or 'both'
        
    Returns
    -------
    dict
        Mapping of format to output path for generated reports
    """
    output_paths = {}
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    # Sanitize variant label for filename
    safe_label = variant_label.replace(":", "_").replace(">", "_").replace(" ", "_")
    
    if formats in ("html", "both"):
        html_path = output_dir_path / f"{safe_label}.html"
        generate_html_report(result, str(html_path))
        output_paths["html"] = str(html_path)
        print(f"   ✓ HTML report saved to: {html_path}")
    
    if formats in ("pdf", "both"):
        pdf_path = output_dir_path / f"{safe_label}.pdf"
        try:
            generate_pdf_report(result, str(pdf_path))
            output_paths["pdf"] = str(pdf_path)
            print(f"   ✓ PDF report saved to: {pdf_path}")
        except ImportError as e:
            print(f"   ⚠ PDF generation skipped: {e}")
        except Exception as e:
            print(f"   ⚠ PDF generation failed: {e}")
    
    return output_paths
