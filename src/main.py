# src/main.py
import argparse   # NEW
import logging
import asyncio
import sys
import os
from pathlib import Path
from workflow import (
    display_mermaid_diagram,
    test_agents,
    run_coordination_workflow,
    logger,
    save_newsletter,
    NewsletterState,
)
from agents import get_agents  # ArxivPaper unused here, but harmless

# -----------------------------------------------------------
# 1) Parse CLI args **here** and expose chosen model globally
# -----------------------------------------------------------
def parse_cli_args() -> str:
    parser = argparse.ArgumentParser(
        description="AI Agents Newsletter Generator"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.0-flash",
        help=(
            'LLM identifier to use for all agents. '
            'Examples: "mistral:mistral-small-latest", '
            '"groq:llama-3.3-70b-versatile", "gemini-2.0-flash"'
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("test", "mermaid"),
        help="Optional sub-command: test agents or show workflow diagram",
    )
    return parser.parse_args()

# -----------------------------------------------------------

def configure_logging():
    """Configure logging for the main script."""
    log_dir = Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / 'newsletter_workflow.log')
        ]
    )

async def main(model: str):
    """Main entry point for the newsletter agent."""
    logger.info("Starting Simple Newsletter Agent...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Selected model: {cli_args.model}")

    # Check environment variables
    required_vars = ['TAVILY_API_KEY', 'GEMINI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file and ensure all required API keys are set.")
        sys.exit(1)

    logger.info("✓ All required environment variables are set")

    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"✓ Data directory ready: {data_dir}")

    # Handle command / flags
    if cli_args.command == "mermaid":
        logger.info("Displaying workflow diagrams...")
        display_mermaid_diagram(*get_agents(model))
        return
    elif cli_args.command == "test":
        logger.info("Testing agent connections...")
        return await test_agents(*get_agents(model))
    else:
        logger.info("Running newsletter generation...")
        
        return await run_coordination_workflow(*get_agents(model))

if __name__ == "__main__":
    configure_logging()
    cli_args = parse_cli_args()

    # Optional: load previous state if it exists
    data_dir = Path("./_data")
    final_state_path = data_dir / "_final_state.pkl"
    if final_state_path.exists():
        logger.info(f"Loading previous outputs from {final_state_path}")
        try:
            import pickle
            with open(final_state_path, "rb") as f:
                alloutputs = pickle.load(f)
            logger.info("✓ Previous outputs loaded successfully")
            print(alloutputs)
            save_newsletter(alloutputs)
        except Exception as e:
            logger.error(f"Failed to load previous outputs: {e}")
    else:
        try:
            result = asyncio.run(main(cli_args.model))
            if result:
                try:
                    import pickle
                    final_state = result[0] if isinstance(result, tuple) else result
                    graph_state = result[1] if isinstance(result, tuple) else None
                    data_dir = Path("./data")
                    with open(data_dir / "final_state.pkl", "wb") as f:
                        pickle.dump(final_state, f)
                    if graph_state:
                        with open(data_dir / "graph_state.pkl", "wb") as f:
                            pickle.dump(graph_state, f)
                    logger.info("✓ State files saved for debugging")
                except Exception as e:
                    logger.warning(f"Could not save state files: {e}")
            logger.info("✓ Newsletter generation completed successfully!")
        except KeyboardInterrupt:
            logger.info("Newsletter generation interrupted by user")
            sys.exit(0)
        except Exception as e:
            logger.exception("An error occurred during execution:")
            sys.exit(1)