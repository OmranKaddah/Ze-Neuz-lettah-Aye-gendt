from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Union, Optional
import asyncio
import logging
import pickle

from pydantic_graph import (
    BaseNode,
    End,
    Graph,
    GraphRunContext,
)
from agents import (
    ArxivPaper, 
    AiItem,
    NewsletterHeader
)
from newsletter_formatter import save_newsletter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class NewsletterState:
    """
    State for the Newsletter Workflow using pydantic_graph.
    """
    arxiv_papers: List[ArxivPaper] = field(default_factory=list)
    ai_items: List[AiItem] = field(default_factory=list)
    header: Optional[NewsletterHeader] = None
    newsletter_content: str = ""
    arxiv_completed: bool = False
    ai_items_completed: bool = False
    arxiv_failed: bool = False  # Track if ArXiv search failed
    ai_items_failed: bool = False  #


@dataclass
class SearchArxivPapers(BaseNode[NewsletterState]):
    """
    Node to search for arXiv papers using the MCP server.
    """
    def __init__(self, research_arxiv_agent):
        super().__init__()
        self.research_arxiv_agent = research_arxiv_agent

    async def run(self, ctx: GraphRunContext[NewsletterState]) -> CheckBothCompleted:
        """
        Search for arXiv papers and mark as completed.
        """
        logger.info("Searching for arXiv papers...")
        
        try:
            response = await self.research_arxiv_agent.run("""
                Find the 3 most recent arXiv papers related to artificial intelligence and agentic systems.
            """)
            
            ctx.state.arxiv_papers.extend(response.output)
            logger.info(f"Found {len(response.output)} arXiv papers")
                
        except asyncio.TimeoutError:
            logger.error("ArXiv search timed out after 60 seconds")
            ctx.state.arxiv_failed = True
        except Exception as e:
            logger.exception("Error searching arXiv papers")
            ctx.state.arxiv_failed = True

        # Mark arxiv search as completed
        ctx.state.arxiv_completed = True
        logger.info("ArXiv search completed")
        
        return CheckBothCompleted()


@dataclass
class SearchAiItems(BaseNode[NewsletterState]):
    """
    Node to search for AI-related items using the Tavily MCP server.
    """
    def __init__(self, search_agent):
        super().__init__()
        self.search_agent = search_agent

    async def run(self, ctx: GraphRunContext[NewsletterState]) -> CheckBothCompleted:
        """
        Search for AI items and mark as completed.
        """
        logger.info("Searching for AI items...")
        
        try:
            response = await self.search_agent.run("""
                Find the latest updates on artificial intelligence and agentic systems, specifically:
                    * 2 recent news releases or announcements about tools or frameworks
                    * 1–2 tutorials
                    * Up to 4 relevant news articles
                    Please provide the title, source, publication date, and link for each.
            """)
            
            ctx.state.ai_items.extend(response.output)
            logger.info(f"Found {len(response.output)} AI items")
                
        except asyncio.TimeoutError:
            logger.error("AI items search timed out after 60 seconds")
            ctx.state.ai_items_failed = True
        except Exception as e:
            logger.exception("Error searching AI items")
            ctx.state.ai_items_failed = True

        # Mark AI items search as completed
        ctx.state.ai_items_completed = True
        logger.info("AI items search completed")
        
        return CheckBothCompleted()


@dataclass
class CheckBothCompleted(BaseNode[NewsletterState]):
    """
    Node to check if both searches are completed before proceeding to header generation.
    """
    def __init__(self, newsletter_header_agent = None):
        super().__init__()
        self.newsletter_header_agent = newsletter_header_agent
    
    def set_agent(self, newsletter_header_agent):
        """
        Set the newsletter header agent if not provided in constructor.
        """
        self.newsletter_header_agent = newsletter_header_agent

    async def run(self, ctx: GraphRunContext[NewsletterState]) -> Union[GenerateNewsletterHeader, WaitForCompletion]:
        """
        Check if both searches are completed, if so proceed to header generation.
        """
        logger.info(f"Checking completion status: ArXiv={ctx.state.arxiv_completed}, AI Items={ctx.state.ai_items_completed}")
        
        if ctx.state.arxiv_completed and ctx.state.ai_items_completed:
            logger.info("Both searches completed, proceeding to header generation")
            
            # Log any failures
            if ctx.state.arxiv_failed:
                logger.warning("ArXiv search failed, proceeding with available content")
            if ctx.state.ai_items_failed:
                logger.warning("AI items search failed, proceeding with available content")
            
            return GenerateNewsletterHeader(self.newsletter_header_agent)
        else:
            logger.info("Waiting for other search to complete...")
            return WaitForCompletion(self.newsletter_header_agent)


@dataclass
class WaitForCompletion(BaseNode[NewsletterState]):
    """
    Node that waits and then checks again if both searches are completed.
    """
    def __init__(self, newsletter_header_agent = None):
        super().__init__()
        self.newsletter_header_agent = newsletter_header_agent
    
    def set_agent(self, newsletter_header_agent):
        """
        Set the newsletter header agent if not provided in constructor.
        """
        self.newsletter_header_agent = newsletter_header_agent

    async def run(self, ctx: GraphRunContext[NewsletterState]) -> Union[GenerateNewsletterHeader, WaitForCompletion]:
        """
        Wait a bit and check again if both searches are completed.
        """
        # Small delay to prevent busy waiting
        await asyncio.sleep(0.1)
        
        logger.debug(f"Re-checking completion status: ArXiv={ctx.state.arxiv_completed}, AI Items={ctx.state.ai_items_completed}")
        
        if ctx.state.arxiv_completed and ctx.state.ai_items_completed:
            logger.info("Both searches now completed, proceeding to header generation")
            return GenerateNewsletterHeader(self.newsletter_header_agent)
        else:
            return WaitForCompletion(self.newsletter_header_agent)


@dataclass
class GenerateNewsletterHeader(BaseNode[NewsletterState]):
    """
    Node to generate a catchy newsletter header summarizing the content.
    """
    def __init__(self, newsletter_header_agent):
        super().__init__()
        self.newsletter_header_agent = newsletter_header_agent

    async def run(self, ctx: GraphRunContext[NewsletterState]) -> GenerateNewsletterContent:
        """
        Generate newsletter header and proceed to content generation.
        """
        logger.info("Generating newsletter header...")
        
        # Check if we have any content to generate header from
        if not ctx.state.ai_items and not ctx.state.arxiv_papers:
            logger.error("No content found to generate header from")
            # Create a default header if no content is available
            ctx.state.header = NewsletterHeader(
                title="AI Agent Newsletter: Content Search Issues",
                headlines="We encountered some technical difficulties gathering content. Please check back later for the latest AI developments!"
            )
            return GenerateNewsletterContent()
        
        prompt = (
            "Generate a catchy newsletter header that consists of a title for the newsletter with about 5 to 15 words, then a summary of the following content:\n\n"
        )

        if ctx.state.ai_items:
            prompt += "AI-Related Items (category, title):\n"
            for item in ctx.state.ai_items:
                prompt += f"- {item.category}: {item.title}\n"
        
        if ctx.state.arxiv_papers:
            prompt += "\nArXiv Papers:\n"
            for paper in ctx.state.arxiv_papers:
                prompt += f"- {paper.title}\n"
        
        # Add note about any failures
        if ctx.state.arxiv_failed and ctx.state.ai_items_failed:
            prompt += "\nNote: Both content searches had technical issues, generating header for available content."
        elif ctx.state.arxiv_failed:
            prompt += "\nNote: ArXiv search had technical issues, focusing on AI items."
        elif ctx.state.ai_items_failed:
            prompt += "\nNote: AI items search had technical issues, focusing on research papers."
        
        try:
            response = await asyncio.wait_for(
                self.newsletter_header_agent.run(prompt),
                timeout=30  # 30 second timeout for header generation
            )
            ctx.state.header = response.output
            
            logger.info(f"Generated header: {response.output}")
            return GenerateNewsletterContent()
            
        except asyncio.TimeoutError:
            logger.error("Header generation timed out")
            ctx.state.header = NewsletterHeader(
                title="AI Agent Newsletter: Latest Updates",
                headlines="Discover the latest developments in AI agents and technologies"
            )
            return GenerateNewsletterContent()
        except Exception as e:
            logger.exception("Error generating newsletter header")
            # Create a fallback header
            ctx.state.header = NewsletterHeader(
                title="AI Agent Newsletter: Latest Updates",
                headlines="Discover the latest developments in AI agents and technologies"
            )
            return GenerateNewsletterContent()


@dataclass
class GenerateNewsletterContent(BaseNode[NewsletterState, None, str]):
    """
    Node to generate and save the final newsletter content.
    """
    async def run(self, ctx: GraphRunContext[NewsletterState]) -> End[str]:
        """
        Generate and save newsletter content, then end the workflow.
        """
        logger.info("Generating newsletter content...")
        
        try:
            # Ensure we have a header before saving
            if ctx.state.header is None:
                ctx.state.header = NewsletterHeader(
                    title="AI Agent Newsletter",
                    headlines="Latest developments in AI and agent technologies"
                )
                        
            # Add notes about any failures
            if ctx.state.arxiv_failed or ctx.state.ai_items_failed:
                failure_notes = []
                if ctx.state.arxiv_failed:
                    failure_notes.append("ArXiv search failed")
                if ctx.state.ai_items_failed:
                    failure_notes.append("AI items search failed")
                summary += f" (Note: {', '.join(failure_notes)})"
            
            logger.info("Newsletter generation completed successfully!")
            return End(summary)
            
        except Exception as e:
            logger.exception("Error generating newsletter content")
            return End(f"Error generating newsletter: {str(e)}")

        

def get_graph_state(research_arxiv_agent, search_agent, newsletter_header_agent) -> Graph[NewsletterState]:
    """
    Returns the graph state for the newsletter workflow.
    This is used to visualize the workflow and its nodes.
    """
    return Graph(
        nodes=(
            SearchArxivPapers(research_arxiv_agent),
            SearchAiItems(search_agent),
            CheckBothCompleted(newsletter_header_agent),
            WaitForCompletion(newsletter_header_agent),
            GenerateNewsletterHeader(newsletter_header_agent),
            GenerateNewsletterContent()
        ),
        state_type=NewsletterState
    )


async def run_coordination_workflow(research_arxiv_agent, search_agent, newsletter_header_agent):
    """
    Run the newsletter workflow using coordination nodes approach.
    """
    logger.info("Starting coordination-based newsletter workflow...")
    
    state = NewsletterState()
    newsletter_graph = get_graph_state(research_arxiv_agent, search_agent, newsletter_header_agent)

    async def start_searches():
        search_arxiv_node = SearchArxivPapers(research_arxiv_agent)
        search_ai_node = SearchAiItems(search_agent)
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    search_arxiv_node.run(GraphRunContext(state=state, deps=None)),
                    search_ai_node.run(GraphRunContext(state=state, deps=None)),
                    return_exceptions=True
                ),
                timeout=120  # 2 minute overall timeout for both searches
            )
            
            # Both should return CheckBothCompleted, so we can use either one
            return results[0] if not isinstance(results[0], Exception) else results[1]
            
        except asyncio.TimeoutError:
            logger.error("Overall search process timed out after 2 minutes")
            # Mark both as completed so we can proceed
            state.arxiv_completed = True
            state.ai_items_completed = True
            state.arxiv_failed = True
            state.ai_items_failed = True
            return CheckBothCompleted()

    
    # Start with parallel searches
    next_node = await start_searches()
    if isinstance(next_node, CheckBothCompleted):
        next_node.set_agent(newsletter_header_agent)
        # next_node = CheckBothCompleted(newsletter_header_agent)
        # with open("inter_state.pkl", "rb") as f:
        #     state = pickle.load(f)    
        # Continue with the graph execution
        result = await newsletter_graph.run(next_node, state=state)
        logger.info("\nWorkflow completed!")
        logger.info(f"Found {len(state.arxiv_papers)} arXiv papers")
        logger.info(f"Found {len(state.ai_items)} AI items")
        logger.info(f"Final result: {result.output}")
        
        
    else:
        result = End("Error in parallel execution")

    return state, result



async def test_agents(research_arxiv_agent, search_agent, newsletter_header_agent):
    """Test individual agents to diagnose connection issues."""
    logger.info("Testing agents...")
    
    # Test research_arxiv_agent
    logger.info("\n1. Testing research_arxiv_agent...")
    try:
        response = await asyncio.wait_for(
            research_arxiv_agent.run("Test connection - find 1 recent AI paper"),
            timeout=30
        )
        logger.info("✓ research_arxiv_agent: Connected successfully")
        logger.info(f"  Response type: {type(response.output)}")
        if hasattr(response, 'output') and response.output:
            logger.info(f"  Found {len(response.output)} items")
    except asyncio.TimeoutError:
        logger.error("✗ research_arxiv_agent: Timed out after 30 seconds")
    except Exception as e:
        logger.error(f"✗ research_arxiv_agent: Failed - {e}")
    
    # Test search_agent
    logger.info("\n2. Testing search_agent...")
    try:
        response = await asyncio.wait_for(
            search_agent.run("Test connection - find latest AI news"),
            timeout=30
        )
        logger.info("✓ search_agent: Connected successfully")
        logger.info(f"  Response type: {type(response.output)}")
        if hasattr(response, 'output') and response.output:
            logger.info(f"  Found {len(response.output)} items")
    except asyncio.TimeoutError:
        logger.error("✗ search_agent: Timed out after 30 seconds")
    except Exception as e:
        logger.error(f"✗ search_agent: Failed - {e}")
    
    # Test newsletter_header_agent
    logger.info("\n3. Testing newsletter_header_agent...")
    try:
        response = await asyncio.wait_for(
            newsletter_header_agent.run("Generate a test header for AI newsletter"),
            timeout=30
        )
        logger.info("✓ newsletter_header_agent: Connected successfully")
        logger.info(f"  Response type: {type(response.output)}")
        if hasattr(response, 'output'):
            logger.info(f"  Generated header: {response.output}")
    except asyncio.TimeoutError:
        logger.error("✗ newsletter_header_agent: Timed out after 30 seconds")
    except Exception as e:
        logger.error(f"✗ newsletter_header_agent: Failed - {e}")


def display_mermaid_diagram(research_arxiv_agent, search_agent, newsletter_header_agent):
    """Display the mermaid diagram for visualization."""
    newsletter_graph = get_graph_state(research_arxiv_agent, search_agent, newsletter_header_agent)
    logger.info("Newsletter workflow mermaid diagram:")
    logger.info(newsletter_graph.mermaid_code(start_node=CheckBothCompleted))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "mermaid":
        display_mermaid_diagram()
        exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_agents())
    else:
        logger.info("Usage:")
        logger.info("  python workflow.py        # Run newsletter generation")
        logger.info("  python workflow.py test   # Test agent connections")
        logger.info("  python workflow.py mermaid # Show workflow diagrams")
        logger.info("\nRunning newsletter generation...")
        result = asyncio.run(run_coordination_workflow())

        import pickle
        final_state = result[0] if isinstance(result, tuple) else result
        graph_state = result[1] if isinstance(result, tuple) else None
        with open("final_state.pkl", "wb") as f:
            pickle.dump(final_state, f)
        with open("graph_state.pkl", "wb") as f:
            pickle.dump(graph_state, f)
