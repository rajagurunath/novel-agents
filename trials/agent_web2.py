import streamlit as st
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import time
import asyncio
import re      # Added for manual tool call parsing
import ast     # Added for manual tool call parsing
import inspect # Added for inspecting tool function signatures

# --- Agent Configuration ---

# IO Intelligence API configuration
IO_API_KEY = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjJlNWNiNzA0LTdiNWEtNDFjOS04NjQ5LTA4ZWFhNzZiYmJhNSIsImV4cCI6NDkwMjk3NDkxNn0.pa3cp35NXcgaJZCWJ7Y0ozWh7Jv1omodrBcTkbz96RQxTr7KdEB4gxidydpSUfCM3_jPNqZVYjaCDZ423g58Jw"
IO_BASE_URL = "https://api.intelligence.io.solutions/api/v1"

# The data store for our agent, managed by Streamlit's session state.
if 'person_address' not in st.session_state:
    st.session_state.person_address = {
        'guru': '3N2k1z5Z7g8d9f4e2b6c3a1b2d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2',
        'madhur': '1A2b3C4d5E6f7G8h9I0j1K2l3M4n5O6p7Q8r9S0t1U2v3W4x5Y6z7A8b9C0d1E2',
        'shivam': '9Z8Y7X6W5V4U3T2S1R0Q9P8O7N6M5L4K3J2I1H0G9F8E7D6C5B4A3Z2Y1X0W9V8',
        'gaurav': '2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5Y6Z7A8B9C0D1E2F3G4',
    }

# Define the Agent
model = OpenAIModel(
    model_name='Qwen/Qwen3-235B-A22B-FP8',
    provider=OpenAIProvider(base_url=IO_BASE_URL, api_key=IO_API_KEY),
)

novel_salary_agent = Agent(
    model=model,
    deps_type=None,
    output_type=str,
    # auto_execute_tools is True, but we have a manual fallback just in case.
    auto_execute_tools=True,
    system_prompt=(
        '''
        YOU are a Novel Salary Agent.
        Your primary role is to manage Solana wallet addresses and simulate SOL transfers.
        When a user asks for information (e.g., a wallet address) or to perform an action (e.g., add a person, transfer SOL),
        you MUST use your available tools to get the information or perform the action.
        After the tool has executed, you MUST provide a clear, natural language response to the user that directly answers their query or confirms the action, incorporating the result from the tool.
        For example, if asked for a wallet address, respond with "The wallet address for [person] is [address]." not just the address.
        If an action is performed, confirm it like "Successfully added [person] with address [address]." or "Successfully transferred [amount] SOL from [person1] to [person2]."

        Available actions:
          - Show the wallet address of a person.
          - Add a new person with their wallet address.
          - Transfer Solana SOL from one person to another.
        Always use your tools to perform these actions and then report the outcome clearly.
        '''
    ),
)


# --- Agent Tools (with original signatures) ---


@novel_salary_agent.tool_plain
def list_persons_with_addresses() -> str:
    """List all persons and their wallet addresses"""
    if not st.session_state.person_address:
        return "No persons found in the system."
    return "\n".join([f"{person}: {address}" for person, address in st.session_state.person_address.items()])

@novel_salary_agent.tool_plain
async def show_wallet_address(person: str) -> str:
    """show the wallet address of a person"""
    return st.session_state.person_address.get(person, f'Person "{person}" not found in the system.')

@novel_salary_agent.tool
async def add_person(ctx: RunContext[str], person: str, address: str) -> str:
    """add a new person with their wallet address"""
    if person in st.session_state.person_address:
        return f'"{person}" already exists in the system.'
    st.session_state.person_address[person] = address
    return f'"{person}" has been added with address {address}.'

@novel_salary_agent.tool
async def transfer_sol(ctx: RunContext[str], from_person: str, to_person: str, amount: float) -> str:
    """transfer solana SOL from one person to another"""
    if from_person not in st.session_state.person_address or to_person not in st.session_state.person_address:
        return "One or both persons not found in the system."
    time.sleep(1) # Simulate network delay
    from_address = st.session_state.person_address[from_person]
    to_address = st.session_state.person_address[to_person]
    return f"Transferred {amount} SOL from {from_person} ({from_address}) to {to_person} ({to_address})."

# Manual mapping of tool names to functions for our parsing logic
tool_functions = {
    "show_wallet_address": show_wallet_address,
    "add_person": add_person,
    "transfer_sol": transfer_sol,
}

# --- Streamlit Application UI ---

st.set_page_config(page_title="Novel Salary Agent Chat", page_icon="💸")

st.title("💸 Novel Salary Agent")
st.caption("I can manage Solana wallets and simulate SOL transfers for you.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Main chat input and processing logic
if prompt := st.chat_input("Ask me to transfer SOL or show an address..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            async def get_response():
                agent_response_obj = await novel_salary_agent.run(prompt)
                agent_output_text = agent_response_obj.output if hasattr(agent_response_obj, 'output') else None
                final_response_to_user = agent_output_text

                if agent_output_text and agent_output_text.startswith("[") and agent_output_text.endswith(")]"):
                    match = re.fullmatch(r"\[(\w+)\((.*)\)\]", agent_output_text)
                    if match:
                        tool_name_str, args_str = match.groups()

                        if tool_name_str in tool_functions:
                            tool_func = tool_functions[tool_name_str]
                            kwargs = {}
                            try:
                                # CORRECTED BLOCK: Using your original, robust parsing logic
                                if args_str.strip():
                                    arg_pairs = args_str.split(',')
                                    temp_kwargs = {}
                                    for pair in arg_pairs:
                                        pair = pair.strip()
                                        if not pair:
                                            continue
                                        if '=' not in pair:
                                            raise ValueError(f"Argument pair '{pair}' is not a valid key=value format.")
                                        
                                        key, value_str = pair.split('=', 1)
                                        key = key.strip()
                                        value_str = value_str.strip()
                                        
                                        temp_kwargs[key] = ast.literal_eval(value_str)
                                    kwargs = temp_kwargs

                                # Inspect and call the tool function
                                sig = inspect.signature(tool_func)
                                if 'ctx' in sig.parameters:
                                    tool_result = await tool_func(ctx=None, **kwargs)
                                else:
                                    tool_result = await tool_func(**kwargs)

                                final_response_to_user = str(tool_result)

                            except Exception as e:
                                final_response_to_user = f"Error during tool execution: {e}"
                
                return final_response_to_user

            try:
                response_text = asyncio.run(get_response())
                if response_text is None:
                    response_text = "I received an empty response. Please try again."
            except Exception as e:
                response_text = f"A critical error occurred: {e}"
        
        st.markdown(response_text)

    st.session_state.messages.append({"role": "assistant", "content": response_text})

    # {'receuver','token','amount'}