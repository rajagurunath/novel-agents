import streamlit as st
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import time
import asyncio

# --- Agent Configuration ---

# IO Intelligence API configuration
IO_API_KEY = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjJlNWNiNzA0LTdiNWEtNDFjOS04NjQ5LTA4ZWFhNzZiYmJhNSIsImV4cCI6NDkwMjk3NDkxNn0.pa3cp35NXcgaJZCWJ7Y0ozWh7Jv1omodrBcTkbz96RQxTr7KdEB4gxidydpSUfCM3_jPNqZVYjaCDZ423g58Jw"
IO_BASE_URL = "https://api.intelligence.io.solutions/api/v1"

# The data store for our agent, initialized here.
# In a real-world app, this might be a database.
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
    auto_execute_tools=True, # Auto-execution is key for seamless operation
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


# --- Agent Tools ---
# Note: Tools now access the person_address dictionary from st.session_state

@novel_salary_agent.tool_plain
async def show_wallet_address(person: str) -> str:
    """show the wallet address of a person"""
    return st.session_state.person_address.get(person, f'Person "{person}" not found in the system.')

@novel_salary_agent.tool_plain
async def add_person(person: str, address: str) -> str:
    """add a new person with their wallet address"""
    if person in st.session_state.person_address:
        return f'"{person}" already exists in the system.'
    st.session_state.person_address[person] = address
    return f'"{person}" has been added with address {address}.'

@novel_salary_agent.tool_plain
async def transfer_sol(from_person: str, to_person: str, amount: float) -> str:
    """transfer solana SOL from one person to another"""
    if from_person not in st.session_state.person_address or to_person not in st.session_state.person_address:
        return "One or both persons not found in the system."
    
    # Simulate the transfer delay
    time.sleep(1)
    
    from_address = st.session_state.person_address[from_person]
    to_address = st.session_state.person_address[to_person]
    return f"Transferred {amount} SOL from {from_person} ({from_address}) to {to_person} ({to_address})."


# --- Streamlit Application UI ---

st.set_page_config(page_title="Novel Salary Agent Chat", page_icon="💸")

st.title("💸 Novel Salary Agent")
st.caption("I can manage Solana wallets and simulate SOL transfers for you.")

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display past messages from the chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Main chat input and processing logic
if prompt := st.chat_input("Ask me to transfer SOL or show an address..."):
    # Add user message to session state and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent's response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Use asyncio.run to execute the async agent function
                agent_response = asyncio.run(novel_salary_agent.run(prompt))
                response_text = agent_response.output
                
            except Exception as e:
                response_text = f"An error occurred: {e}"
        
        st.markdown(response_text)

    # Add agent's response to session state
    st.session_state.messages.append({"role": "assistant", "content": response_text})