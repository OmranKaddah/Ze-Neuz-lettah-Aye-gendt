# src/agents.py
from datetime import datetime, timedelta
from typing import List, Literal, Optional
import os
import logging

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.common_tools.tavily import tavily_search_tool

import os

logger = logging.getLogger(__name__)


class AiItem(BaseModel):
    title: str = Field(description="Title of the AI-related item")
    summary: str = Field(description="Summary of AI-related item")
    source: str = Field(description="Source URL of the AI-related item")
    # category should be of type categorical tool
    category: Literal['tool', 'framework', 'tutorial', 'news'] = Field(
        description="Category of the AI item"
    )
    published_date: datetime = Field(
        description="Publication date of the AI item",
        default_factory=lambda: datetime.now() - timedelta(days=30)  # Default to last 30 days
    )


class ArxivPaper(AiItem):
    findings: str = Field(description="Key findings of the paper")
    published_date: datetime = Field(
        description="Publication date of the paper",
        default_factory=lambda: datetime.now() - timedelta(days=30)  # Default to last 30 days
    )
    category: Literal["Arxiv Paper"] = Field('Arxiv Paper', description="Category of the item, always 'Arxiv Paper' for ArxivPaper")

class NewsletterHeader(BaseModel):
    title : str = Field(description="Newsletter title")
    headlines: str = Field(
        description="Headlines for the newsletter - a catchy, funny and engaging summary of the latest developments in AI agents",
    )

# twitter_server = MCPServerStdio(
#     command = "npx",
#     args = [
#         "-y", 
#         "@enescinar/twitter-mcp"
#     ],
#     env=
#     {
#         "API_KEY": "your_api_key_here",
#         "API_SECRET_KEY": "your_api_secret_key_here",
#         "ACCESS_TOKEN": "your_access_token_here",
#         "ACCESS_TOKEN_SECRET": "your_access_token_secret_here"
#     }
# )
def get_agents(model: str = 'gemini-2.0-flash') -> List[Agent]:
    """
    Returns a list of configured agents for the newsletter workflow.
    """

    # Try different ways to set up the ArXiv server depending on environment
    try:
        logger.info("Using uv tool run for ArXiv MCP server")
        arxiv_server = MCPServerStdio(
            command="uv",
            args=[
                "tool",
                "run",
                "arxiv-mcp-server",
            ],
            timeout=30  # Add timeout
        )
    except Exception as e:
        logger.warning(f"Failed to setup ArXiv MCP server: {e}")
        arxiv_server = None

    # Create research agent with or without ArXiv server
    if arxiv_server:
        research_arxiv_agent = Agent(
            model=model,
            output_type=List[ArxivPaper],
            system_prompt="""
            You are an AI research specialist focused on agent development.
            Search for and analyze the latest papers using the ArXiv MCP server.
            
            Focus on:
            - Research papers on agent architectures
            - Multi-agent systems
            - AI agent frameworks and tools

            Provide structured summaries with key findings.
            """,
            toolsets=[arxiv_server]
        )
    else:
        # Fallback: use Tavily search for research papers
        logger.warning("ArXiv MCP server not available, using Tavily search as fallback")
        research_arxiv_agent = Agent(
            model=model,
            output_type=List[ArxivPaper],
            system_prompt="""
            You are an AI research specialist focused on agent development.
            Search for and analyze the latest research papers using web search.
            
            Focus on:
            - Recent arXiv papers on agent architectures
            - Multi-agent systems research
            - AI agent frameworks and tools
            
            When you find papers, structure them as ArxivPaper objects with proper findings.
            Look for papers from arxiv.org, academic conferences, and research institutions.
            """,
            tools=[tavily_search_tool(os.environ['TAVILY_API_KEY'] )]
        )

    search_agent = Agent(
        model=model,
        output_type=List[AiItem],
        system_prompt="""
        You are an AI research specialist focused on agent development.
        Search for and analyze the tool-related developments 
        in AI agents, multi-agent systems, and frameworks.
        
        Focus on:
        - New tools and frameworks for agent development
        - Industry developments and announcements
        - Tutorials and educational content
        
        Provide structured summaries with importance scores.
        """,
        tools=[tavily_search_tool(os.environ['TAVILY_API_KEY'] )]
    )

    newsletter_header_agent = Agent(
        model=model,
        output_type=NewsletterHeader,
        system_prompt="""
            You are an AI newsletter editor.
            Create a catchy, funny and engaging newsletter header that summarizes the latest developments in AI agents.
        """,
        tools=[],
    )

    return [
        research_arxiv_agent,
        search_agent,
        newsletter_header_agent,
    ]