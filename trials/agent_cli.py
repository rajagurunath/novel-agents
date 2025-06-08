from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import time
import asyncio # Added asyncio
import re # Added for manual tool call parsing
import ast # Added for manual tool call parsing
import inspect # Added for inspecting tool function signatures



# IO Intelligence API configuration
IO_API_KEY = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjJlNWNiNzA0LTdiNWEtNDFjOS04NjQ5LTA4ZWFhNzZiYmJhNSIsImV4cCI6NDkwMjk3NDkxNn0.pa3cp35NXcgaJZCWJ7Y0ozWh7Jv1omodrBcTkbz96RQxTr7KdEB4gxidydpSUfCM3_jPNqZVYjaCDZ423g58Jw"

# Correct IO Intelligence API endpoint
IO_BASE_URL = "https://api.intelligence.io.solutions/api/v1"

model = OpenAIModel(
    model_name='meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8', provider=OpenAIProvider(base_url=IO_BASE_URL, api_key=IO_API_KEY),
)

person_address = {
    'guru': '3N2k1z5Z7g8d9f4e2b6c3a1b2d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2',
    'madhur': '1A2b3C4d5E6f7G8h9I0j1K2l3M4n5O6p7Q8r9S0t1U2v3W4x5Y6z7A8b9C0d1E2',
    'shivam': '9Z8Y7X6W5V4U3T2S1R0Q9P8O7N6M5L4K3J2I1H0G9F8E7D6C5B4A3Z2Y1X0W9V8',
    'gaurav': '2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5Y6Z7A8B9C0D1E2F3G4',
}

novel_salary_agent = Agent(  
    model=model,
    deps_type=str,
    auto_execute_tools=True, # Explicitly set
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

@novel_salary_agent.tool_plain
def list_persons_with_addresses() -> str:
    """List all persons and their wallet addresses"""
    if not person_address:
        return "No persons found in the system."
    return "\n".join([f"{person}: {address}" for person, address in person_address.items()])

@novel_salary_agent.tool_plain
async def show_wallet_address(person: str) -> str:  
    """show the wallet address of a person"""
    return person_address.get(person, 'Person not found in the system.')


@novel_salary_agent.tool
async def add_person(ctx: RunContext[str], person: str, address: str) -> str:
    """add a new person with their wallet address"""
    if person in person_address:
        return f"{person} already exists in the system."
    person_address[person] = address
    return f"{person} has been added with address {address}."

@novel_salary_agent.tool
async def transfer_sol(ctx: RunContext[str], from_person: str, to_person: str, amount: float) -> str:
    """transfer solana SOL from one person to another"""
    if from_person not in person_address or to_person not in person_address:
        return "One or both persons not found in the system."
    time.sleep(1)
    # Here we would normally interact with the Solana blockchain to perform the transfer.
    # For this example, we will just simulate the transfer.
    from_address = person_address[from_person]
    to_address = person_address[to_person]
    return f"Transferred {amount} SOL from {from_person} ({from_address}) to {to_person} ({to_address}). "

# Manual mapping of tool names to functions for workaround
tool_functions = {
    "show_wallet_address": show_wallet_address,
    "add_person": add_person,
    "transfer_sol": transfer_sol,
}

async def main():
    """Main function to run the interactive terminal agent."""
    print("Novel Salary Agent: Interactive Terminal")
    print("Type 'exit' or 'quit' to end the session.")
    print("-" * 30)

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting Novel Salary Agent. Goodbye!")
                break

            if not user_input.strip():
                continue

            # Create a new context for each run if necessary, or reuse.
            agent_response_obj = await novel_salary_agent.run(user_input) # Returns AgentRunResult
            agent_output_text = agent_response_obj.output if hasattr(agent_response_obj, 'output') else None

            print(f"DEBUG: Raw agent_output_text from pydantic-ai: {agent_output_text}")

            final_response_to_user = agent_output_text # Default to agent's direct output

            if agent_output_text and agent_output_text.startswith("[") and agent_output_text.endswith(")]"):
                # Attempt to parse as a tool call string like "[tool_name(arg1='val1', arg2=val2)]"
                match = re.fullmatch(r"\[(\w+)\((.*)\)\]", agent_output_text)
                if match:
                    tool_name_str = match.group(1)
                    args_str = match.group(2)
                    
                    print(f"DEBUG: Detected tool call string: {tool_name_str}, args_str: '{args_str}'")

                    if tool_name_str in tool_functions:
                        tool_func = tool_functions[tool_name_str]
                        kwargs = {} # Initialize kwargs
                        if args_str.strip(): # Ensure args_str is not empty or just whitespace
                            try:
                                # Split by comma for multiple arguments
                                arg_pairs = args_str.split(',')
                                temp_kwargs = {}
                                for pair in arg_pairs:
                                    pair = pair.strip()
                                    if not pair: # Skip if pair is empty after strip (e.g. trailing comma)
                                        continue
                                    if '=' not in pair:
                                        raise ValueError(f"Argument pair '{pair}' is not a valid key=value format.")
                                    
                                    key, value_str = pair.split('=', 1)
                                    key = key.strip() # Remove whitespace from key
                                    value_str = value_str.strip() # Remove whitespace from value string
                                    
                                    # Use ast.literal_eval for the value part only
                                    temp_kwargs[key] = ast.literal_eval(value_str)
                                kwargs = temp_kwargs # Assign to kwargs if parsing successful
                                # print(f"DEBUG: Parsed kwargs for tool {tool_name_str}: {kwargs}")
                            except Exception as e_parse:
                                # print(f"DEBUG: Error parsing args_str '{args_str}' for tool {tool_name_str}: {e_parse}")
                                final_response_to_user = f"Error parsing arguments for tool: {agent_output_text}"
                        # If args_str was empty or only whitespace, kwargs remains {}
                        
                        if final_response_to_user == agent_output_text : # No parsing error yet
                            try:
                                # Inspect the tool function's signature
                                sig = inspect.signature(tool_func)
                                if 'ctx' in sig.parameters:
                                    # Call with ctx if the tool expects it
                                    tool_result = await tool_func(ctx=None, **kwargs)
                                else:
                                    # Call without ctx if the tool (e.g., decorated with @tool_plain) doesn't expect it
                                    tool_result = await tool_func(**kwargs)
                                
                                final_response_to_user = str(tool_result)
                                # print(f"DEBUG: Manual tool execution result for {tool_name_str}: {final_response_to_user}")
                            except Exception as e_tool_exec:
                                # print(f"DEBUG: Error manually executing tool {tool_name_str} with kwargs {kwargs}: {e_tool_exec}")
                                final_response_to_user = f"Error executing tool: {agent_output_text}"
                    else:
                        pass
                        # print(f"DEBUG: Detected tool call string for unknown tool: {tool_name_str}")
                        # Keep original agent output if tool is unknown to our manual map
                else:
                    # String looked like a list/array but didn't match tool call pattern, use as is.
                    # print(f"DEBUG: String '{agent_output_text}' resembles a list but not a recognized tool call format.")
                    pass
            # Display the final response to the user
            if final_response_to_user is not None:
                print(f"Novel Agent: {final_response_to_user}")
            else:
                print("Agent: No parsable output received or output is None.")

        except Exception as e:
            print(f"An error occurred: {e}")
        print("-" * 30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting Novel Salary Agent. Goodbye!")
    except Exception as e:
        print(f"A critical error occurred during startup or shutdown: {e}")
