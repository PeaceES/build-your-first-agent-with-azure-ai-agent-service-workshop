import asyncio
import logging
import os

from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import (
    Agent,
    AgentThread,
    AsyncFunctionTool,
    AsyncToolSet,
    BingGroundingTool,
    CodeInterpreterTool,
    FileSearchTool,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from events_data import EventsData
from stream_event_handler import StreamEventHandler
from terminal_colors import TerminalColors as tc
from utilities import Utilities

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

load_dotenv()

AGENT_NAME = "Tutorial Scheduler"
ROOM_GUIDE_FILE = "datasheet/campus-room-guide.pdf"
FONTS_ZIP = "fonts/fonts.zip"
API_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")
PROJECT_CONNECTION_STRING = os.environ["PROJECT_CONNECTION_STRING"]
BING_CONNECTION_NAME = os.getenv("BING_CONNECTION_NAME")
MAX_COMPLETION_TOKENS = 10240
MAX_PROMPT_TOKENS = 20480
# The LLM is used to generate the SQL queries.
# Set the temperature and top_p low to get more deterministic results.
TEMPERATURE = 0.1
TOP_P = 0.1
INSTRUCTIONS_FILE = None


toolset = AsyncToolSet()
utilities = Utilities()
events_data = EventsData(utilities)


project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str=PROJECT_CONNECTION_STRING,
)

functions = AsyncFunctionTool({
    events_data.async_fetch_tutorial_data_using_sqlite_query,
})

#INSTRUCTIONS_FILE = "instructions/campus_guide_file_search.txt"
#INSTRUCTIONS_FILE = "instructions/tutorial_db_instructions.txt"

INSTRUCTIONS_FILE = "instructions/general_instructions.txt"



async def add_agent_tools() -> None:
    """Add tools for the agent."""
    font_file_info = None

    # Add the functions tool
    toolset.add(functions)

    # Add the room guide data sheet to a new vector data store
    vector_store = await utilities.create_vector_store(
         project_client,
         files=[ROOM_GUIDE_FILE],
         vector_store_name="PlannerPro Product Information Vector Store",
    )
    file_search_tool = FileSearchTool(vector_store_ids=[vector_store.id])
    toolset.add(file_search_tool)

    # Add the code interpreter tool
    code_interpreter = CodeInterpreterTool()
    toolset.add(code_interpreter)

    # Add the Bing grounding tool
    # bing_connection = await project_client.connections.get(connection_name=BING_CONNECTION_NAME)
    # bing_grounding = BingGroundingTool(connection_id=bing_connection.id)
    # toolset.add(bing_grounding)

    # Add multilingual support to the code interpreter
    font_file_info = await utilities.upload_file(project_client, utilities.shared_files_path / FONTS_ZIP)
    code_interpreter.add_file(file_id=font_file_info.id)

    return font_file_info


async def initialize() -> tuple[Agent, AgentThread]:
    """Initialize the agent with the events data schema and instructions."""

    if not INSTRUCTIONS_FILE:
        return None, None

    font_file_info = await add_agent_tools()

    await events_data.connect()
    database_schema_string = await events_data.get_database_info()

    try:
        # Load general agent instructions
        instructions = utilities.load_instructions(INSTRUCTIONS_FILE)

        # Add database tool instructions and inject schema
        instructions += "\n\n" + utilities.load_instructions("instructions/tutorial_db_instructions.txt").replace(
            "{database_schema_string}", database_schema_string
        )

        # Add file search instructions
        instructions += "\n\n" + utilities.load_instructions("instructions/campus_guide_file_search.txt")

        # Inject font file ID if needed
        if font_file_info:
            instructions = instructions.replace("{font_file_id}", font_file_info.id)

        print("Creating agent...")
        agent = await project_client.agents.create_agent(
            model=API_DEPLOYMENT_NAME,
            name=AGENT_NAME,
            instructions=instructions,
            toolset=toolset,
            temperature=TEMPERATURE,
            # headers={"x-ms-enable-preview": "true"},
        )
        print(f"Created agent, ID: {agent.id}")

        project_client.agents.enable_auto_function_calls(toolset=toolset)
        print("Enabled auto function calls.")

        print("Creating thread...")
        thread = await project_client.agents.create_thread()
        print(f"Created thread, ID: {thread.id}")

        return agent, thread

    except Exception as e:
        logger.error("An error occurred initializing the agent: %s", str(e))
        logger.error("Please ensure you've enabled an instructions file.")


async def cleanup(agent: Agent, thread: AgentThread) -> None:
    """Cleanup the resources."""
    existing_files = await project_client.agents.list_files()
    for f in existing_files.data:
        await project_client.agents.delete_file(f.id)
    await project_client.agents.delete_thread(thread.id)
    await project_client.agents.delete_agent(agent.id)
    await events_data.close()


async def post_message(thread_id: str, content: str, agent: Agent, thread: AgentThread) -> None:
    """Post a message to the Foundry Agent Service."""
    try:
        await project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=content,
        )

        stream = await project_client.agents.create_stream(
            thread_id=thread.id,
            agent_id=agent.id,
            event_handler=StreamEventHandler(
                functions=functions, project_client=project_client, utilities=utilities),
            max_completion_tokens=MAX_COMPLETION_TOKENS,
            max_prompt_tokens=MAX_PROMPT_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            instructions=agent.instructions,
        )

        async with stream as s:
            await s.until_done()
    except Exception as e:
        utilities.log_msg_purple(
            f"An error occurred posting the message: {e!s}")


async def main() -> None:
    """
    Example questions:  How many tutorials are scheduled for next week?
    """
    async with project_client:
        agent, thread = await initialize()
        if not agent or not thread:
            print(f"{tc.BG_BRIGHT_RED}Initialization failed. Ensure you have uncommented the instructions file for the lab.{tc.RESET}")
            print("Exiting...")
            return

        cmd = None

        while True:
            prompt = input(
                f"\n\n{tc.GREEN}Enter your query (type exit or save to finish): {tc.RESET}").strip()
            if not prompt:
                continue

            cmd = prompt.lower()
            if cmd in {"exit", "save"}:
                break

            await post_message(agent=agent, thread_id=thread.id, content=prompt, thread=thread)

        if cmd == "save":
            print("The agent has not been deleted, so you can continue experimenting with it in the Azure AI Foundry.")
            print(
                f"Navigate to https://ai.azure.com, select your project, then playgrounds, agents playgound, then select agent id: {agent.id}"
            )
        else:
            await cleanup(agent, thread)
            print("The agent resources have been cleaned up.")


if __name__ == "__main__":
    print("Starting async program...")
    asyncio.run(main())
    print("Program finished.")
