# """
# Newsletter formatting utilities for generating HTML and text newsletters.
# """

# src/newsletter_formatter.py
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
import logging
import boto3
from os import environ

logger = logging.getLogger(__name__)

def save_newsletter(state, runs) -> Tuple[Path, Path]:
    """
    Generate and save newsletter in both HTML and text formats.
    
    Args:
        state: NewsletterState object containing arxiv_papers, ai_items, and header
        
    Returns:
        Tuple of (html_file_path, text_file_path)
    """
    # Ensure output directory exists
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if runs == "on_aws":
        html_file = Path(f"ai_newsletter_{timestamp}.html")
        text_file = Path(f"ai_newsletter_{timestamp}.txt")
        # Generate HTML content
        html_content = generate_html_newsletter(state)
        
        # Generate text content
        text_content = generate_text_newsletter(state)
        
        s3 = boto3.client('s3')
        # upload HTML file to S3
        bucket_name = environ.get('S3_BUCKET')        
        s3.put_object(
            Bucket=bucket_name,
            Key=f'newsletters/{html_file.name}',
            Body=html_content,
            ContentType='text/html'
        )
    else:
        output_dir = Path("./output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file = output_dir / f"ai_newsletter_{timestamp}.html"
        text_file = output_dir / f"ai_newsletter_{timestamp}.txt"
        
        # Generate HTML content
        html_content = generate_html_newsletter(state)
        
        # Generate text content
        text_content = generate_text_newsletter(state)
        
        # Save files
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_content)
    
    logger.info(f"Newsletter saved: {html_file.name} and {text_file.name}")
    
    return html_file, text_file


def generate_html_newsletter(state) -> str:
    """Generate HTML newsletter content."""
    
    # Extract header information
    header_title = getattr(state.header, 'title', 'AI Agents Newsletter')
    header_headlines = getattr(state.header, 'headlines', 'Latest AI developments and insights')
    
    # Generate current date
    current_date = datetime.now().strftime("%B %d, %Y")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{header_title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }}
        
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }}
        
        .header .subtitle {{
            font-size: 1.1rem;
            opacity: 0.9;
            margin-bottom: 1rem;
        }}
        
        .header .date {{
            font-size: 0.9rem;
            opacity: 0.8;
        }}
        
        .content {{
            padding: 2rem;
        }}
        
        .section {{
            margin-bottom: 3rem;
        }}
        
        .section-title {{
            font-size: 1.8rem;
            color: #2c3e50;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 3px solid #667eea;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .section-title::before {{
            content: "📚";
            font-size: 1.5rem;
        }}
        
        .section-title.ai-items::before {{
            content: "🚀";
        }}
        
        .item {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border-radius: 0 8px 8px 0;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        
        .item:hover {{
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .item-title {{
            font-size: 1.3rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 0.8rem;
            line-height: 1.4;
        }}
        
        .item-meta {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }}
        
        .meta-item {{
            background: #e9ecef;
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            color: #495057;
        }}
        
        .category {{
            background: #667eea;
            color: white;
        }}
        
        .item-summary {{
            color: #555;
            margin-bottom: 1rem;
            line-height: 1.6;
        }}
        
        .item-findings {{
            background: #e8f4f8;
            padding: 1rem;
            border-radius: 6px;
            margin-bottom: 1rem;
        }}
        
        .findings-label {{
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 0.5rem;
        }}
        
        .item-link {{
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
            padding: 0.5rem 1rem;
            border: 2px solid #667eea;
            border-radius: 25px;
            transition: all 0.3s ease;
        }}
        
        .item-link:hover {{
            background: #667eea;
            color: white;
            transform: translateY(-2px);
        }}
        
        .stats {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            text-align: center;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}
        
        .stat-item {{
            background: rgba(255,255,255,0.2);
            padding: 1rem;
            border-radius: 6px;
        }}
        
        .stat-number {{
            font-size: 2rem;
            font-weight: 700;
            display: block;
        }}
        
        .stat-label {{
            font-size: 0.9rem;
            opacity: 0.9;
        }}
        
        .footer {{
            background: #2c3e50;
            color: white;
            padding: 2rem;
            text-align: center;
        }}
        
        .footer p {{
            margin-bottom: 0.5rem;
        }}
        
        @media (max-width: 600px) {{
            .header h1 {{
                font-size: 2rem;
            }}
            
            .content {{
                padding: 1rem;
            }}
            
            .item {{
                padding: 1rem;
            }}
            
            .item-meta {{
                flex-direction: column;
                gap: 0.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{header_title}</h1>
            <div class="subtitle">{header_headlines}</div>
            <div class="date">{current_date}</div>
        </div>
        
        <div class="content">
            <div class="stats">
                <h3>Newsletter Summary</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <span class="stat-number">{len(state.arxiv_papers)}</span>
                        <span class="stat-label">Research Papers</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">{len(state.ai_items)}</span>
                        <span class="stat-label">AI Updates</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">{len(state.arxiv_papers) + len(state.ai_items)}</span>
                        <span class="stat-label">Total Items</span>
                    </div>
                </div>
            </div>
"""

    # Add ArXiv Papers section
    if state.arxiv_papers:
        html_content += """
            <div class="section">
                <h2 class="section-title">Latest Research Papers</h2>
"""
        for paper in state.arxiv_papers:
            findings_html = ""
            if hasattr(paper, 'findings') and paper.findings:
                findings_html = f"""
                <div class="item-findings">
                    <div class="findings-label">Key Findings:</div>
                    {paper.findings}
                </div>
                """
            
            pub_date = paper.published_date.strftime("%B %d, %Y") if hasattr(paper, 'published_date') and paper.published_date else "Recent"
            
            html_content += f"""
                <div class="item">
                    <div class="item-title">{paper.title}</div>
                    <div class="item-meta">
                        <span class="meta-item category">Research Paper</span>
                        <span class="meta-item">📅 {pub_date}</span>
                    </div>
                    <div class="item-summary">{paper.summary}</div>
                    {findings_html}
                    <a href="{paper.source}" class="item-link" target="_blank">Read Paper →</a>
                </div>
            """
        
        html_content += "            </div>\n"

    # Add AI Items section
    if state.ai_items:
        html_content += """
            <div class="section">
                <h2 class="section-title ai-items">AI Tools & Updates</h2>
"""
        for item in state.ai_items:
            pub_date = item.published_date.strftime("%B %d, %Y") if hasattr(item, 'published_date') and item.published_date else "Recent"
            category_emoji = {
                'tool': '🛠️',
                'framework': '⚡',
                'tutorial': '📖',
                'news': '📰'
            }.get(item.category, '🔹')
            
            html_content += f"""
                <div class="item">
                    <div class="item-title">{item.title}</div>
                    <div class="item-meta">
                        <span class="meta-item category">{category_emoji} {item.category.title()}</span>
                        <span class="meta-item">📅 {pub_date}</span>
                    </div>
                    <div class="item-summary">{item.summary}</div>
                    <a href="{item.source}" class="item-link" target="_blank">Learn More →</a>
                </div>
            """
        
        html_content += "            </div>\n"

    # Close HTML
    html_content += f"""
        </div>
        
        <div class="footer">
            <p><strong>AI Agents Newsletter</strong></p>
            <p>Generated on {current_date}</p>
            <p>Stay updated with the latest in AI and agent technologies!</p>
        </div>
    </div>
</body>
</html>"""

    return html_content


def generate_text_newsletter(state) -> str:
    """Generate plain text newsletter content for email/text distribution."""
    
    header_title = getattr(state.header, 'title', 'AI Agents Newsletter')
    header_headlines = getattr(state.header, 'headlines', 'Latest AI developments and insights')
    current_date = datetime.now().strftime("%B %d, %Y")
    
    text_content = f"""
{'='*60}
{header_title.upper()}
{'='*60}

{header_headlines}

Date: {current_date}
Total Items: {len(state.arxiv_papers) + len(state.ai_items)}
Research Papers: {len(state.arxiv_papers)}
AI Updates: {len(state.ai_items)}

{'='*60}
"""

    # Add ArXiv Papers section
    if state.arxiv_papers:
        text_content += f"\n📚 LATEST RESEARCH PAPERS ({len(state.arxiv_papers)})\n"
        text_content += "-" * 40 + "\n\n"
        
        for i, paper in enumerate(state.arxiv_papers, 1):
            pub_date = paper.published_date.strftime("%B %d, %Y") if hasattr(paper, 'published_date') and paper.published_date else "Recent"
            
            text_content += f"{i}. {paper.title}\n"
            text_content += f"   Date: {pub_date}\n"
            text_content += f"   Summary: {paper.summary}\n"
            
            if hasattr(paper, 'findings') and paper.findings:
                text_content += f"   Key Findings: {paper.findings}\n"
            
            text_content += f"   Link: {paper.source}\n\n"

    # Add AI Items section
    if state.ai_items:
        text_content += f"\n🚀 AI TOOLS & UPDATES ({len(state.ai_items)})\n"
        text_content += "-" * 40 + "\n\n"
        
        for i, item in enumerate(state.ai_items, 1):
            pub_date = item.published_date.strftime("%B %d, %Y") if hasattr(item, 'published_date') and item.published_date else "Recent"
            
            text_content += f"{i}. {item.title}\n"
            text_content += f"   Category: {item.category.title()}\n"
            text_content += f"   Date: {pub_date}\n"
            text_content += f"   Summary: {item.summary}\n"
            text_content += f"   Link: {item.source}\n\n"

    # Footer
    text_content += "\n" + "="*60 + "\n"
    text_content += "AI Agents Newsletter\n"
    text_content += f"Generated on {current_date}\n"
    text_content += "Stay updated with the latest in AI and agent technologies!\n"
    text_content += "="*60 + "\n"

    return text_content