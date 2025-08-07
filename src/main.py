# src/main.py
import argparse   # NEW
import logging
import asyncio
import sys
import os
from pathlib import Path
import boto3
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
        "--runs", 
        type=str,
        default="locally", 
        choices=["locally", "on_aws"],
        help=(
            'Where to run the agents: "locally" or "cloud". '   
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
    # log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / 'newsletter_workflow.log')
        ]
    )

async def main(model: str, command: str = ""):
    """Main entry point for the newsletter agent."""
    logger.info("Starting Simple Newsletter Agent...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Selected model: {model}")

    logger.info("✓ All required environment variables are set")

    # Handle command / flags
    if command == "mermaid":
        logger.info("Displaying workflow diagrams...")
        display_mermaid_diagram(*get_agents(model))
        return
    elif command == "test":
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
    try:
        if cli_args.runs == "on_aws":
            import json
            logger.info("Running on AWS environment")
            secrets = boto3.client('secretsmanager')
            secret   = secrets.get_secret_value(SecretId='newsletter/api-keys')
            os.environ['TAVILY_API_KEY']  = json.loads(secret['SecretString'])['TAVILY_API_KEY']
            logger.info("✓ Tavily API key loaded from AWS Secrets Manager")
            os.environ['GOOGLE_API_KEY'] = json.loads(secret['SecretString'])['GOOGLE_API_KEY']
            logger.info("✓ GOOGLE API key loaded from AWS Secrets Manager")

        result = asyncio.run(main(cli_args.model, cli_args.command))
        save_newsletter(result[0], cli_args.runs)

        logger.info("✓ Newsletter generation completed successfully!")
    except KeyboardInterrupt:
        logger.info("Newsletter generation interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception("An error occurred during execution:")
        sys.exit(1)