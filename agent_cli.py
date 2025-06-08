#!/usr/bin/env python3

import asyncio
import sqlite3
import json
import re
from typing import List

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from pydantic import BaseModel

# --- Configuration ---
DB_FILE = "salary_agent.db"
USDT_TOKEN_ADDRESS = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

# IO Intelligence API configuration
IO_API_KEY = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjJlNWNiNzA0LTdiNWEtNDFjOS04NjQ5LTA4ZWFhNzZiYmJhNSIsImV4cCI6NDkwMjk3NDkxNn0.pa3cp35NXcgaJZCWJ7Y0ozWh7Jv1omodrBcTkbz96RQxTr7KdEB4gxidydpSUfCM3_jPNqZVYjaCDZ423g58Jw"
IO_BASE_URL = "https://api.intelligence.io.solutions/api/v1"

# Initialize Rich Console
console = Console()

ASCII_ART = """
# _____   ___________    ________________ 
# ___  | / /_  __ \_ |  / /__  ____/__  / 
# __   |/ /_  / / /_ | / /__  __/  __  /  
# _  /|  / / /_/ /__ |/ / _  /___  _  /___
# /_/ |_/  \____/ _____/  /_____/  /_____/
"""

# --- Database Setup ---
def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS persons (
                name TEXT PRIMARY KEY,
                address TEXT NOT NULL UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_person TEXT NOT NULL,
                to_person TEXT NOT NULL,
                amount REAL NOT NULL,
                token TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_person) REFERENCES persons (name),
                FOREIGN KEY (to_person) REFERENCES persons (name)
            )
        ''')
        conn.commit()


class TransferUSDCResponse(BaseModel):
    sender: str
    receiver: str
    amount: float
    token: str = USDT_TOKEN_ADDRESS

# --- Agent and Tools ---

model = OpenAIModel(
    model_name='Qwen/Qwen3-235B-A22B-FP8',
    provider=OpenAIProvider(base_url=IO_BASE_URL, api_key=IO_API_KEY),
)

novel_salary_agent = Agent(
    model=model,
    deps_type=str,
    auto_execute_tools=True,
    system_prompt=(
        '''
        YOU are a world-class Novel Salary Agent, an expert in managing Solana wallets and executing SQL queries.

        **Your Response Structure:**
        1.  **Think Step-by-Step:** First, analyze the user's request. Enclose your reasoning in <think> and </think> tags. Inside, explain which tool you will use. If using the SQL tool, write the exact SQL query you will execute.
        2.  **Provide a Final, Clean Answer:** After the </think> tag, give the user the final answer.

        **Available Tools:**
        - You have simple tools for common tasks: `add_person`, `show_wallet_address`, `list_persons_with_addresses`, `transfer_sol`.
        - **For any other database questions, you MUST use the `execute_sql_query` tool.** This is your primary tool for custom data retrieval and analysis.

        **Database Schema for SQL Queries:**
        You have access to the following two tables. Use this schema to construct your queries for the `execute_sql_query` tool.

        ```sql
        CREATE TABLE persons (
            name TEXT PRIMARY KEY,
            address TEXT NOT NULL UNIQUE
        );

        CREATE TABLE transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_person TEXT NOT NULL,
            to_person TEXT NOT NULL,
            amount REAL NOT NULL,
            token TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ```

        **Example Query:** If the user asks "How many transfers has guru made?", you should think:
        "<think>The user wants to count transfers from 'guru'. I will use the `execute_sql_query` tool. The query is: `SELECT COUNT(*) FROM transfers WHERE from_person = 'guru';`</think>"
        Then, after the tool executes, you will present the result to the user. 
        
        Important : for transfer_usdc tool which returns json, make sure to show the json response in a formatted way in output along with your response.
        '''
    ),
)


# --- All Tools ---

@novel_salary_agent.tool_plain
async def execute_sql_query(query: str) -> str:
    """
    Executes a given SQL query on the database.
    Use this for any custom data requests that simple tools cannot handle.
    Returns a formatted table for SELECT queries or a success message for other operations.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            # For SELECT statements, fetch and format the results
            if query.strip().upper().startswith("SELECT"):
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                conn.commit() # Commit is safe even for SELECT

                if not rows:
                    return "Query executed successfully, but returned no results."

                table = Table(title="SQL Query Results", style="cyan", expand=True)
                for col in columns:
                    table.add_column(col, style="magenta")
                for row in rows:
                    table.add_row(*[str(item) for item in row])

                from io import StringIO
                string_io = StringIO()
                temp_console = Console(file=string_io)
                temp_console.print(table)
                return string_io.getvalue()
            
            # For other statements (INSERT, UPDATE, DELETE), return status
            else:
                row_count = cursor.rowcount
                conn.commit()
                return f"Query executed successfully. {row_count} rows affected."

    except sqlite3.Error as e:
        return f"Database Error: {e}"


@novel_salary_agent.tool_plain
def list_persons_with_addresses() -> str:
    """Lists all persons and their wallet addresses from the database."""
    return asyncio.run(execute_sql_query("SELECT name, address FROM persons ORDER BY name"))

@novel_salary_agent.tool_plain
async def show_wallet_address(person: str) -> str:
    """Shows the wallet address of a specific person from the database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT address FROM persons WHERE name = ?", (person.lower(),))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return f"Person '{person}' not found in the system."
    except sqlite3.Error as e:
        return f"Database error: {e}"

@novel_salary_agent.tool_plain
async def add_person(person: str, address: str) -> str:
    """Adds a new person with their wallet address to the database if not already present."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Check if person or address already exists
            cursor.execute("SELECT 1 FROM persons WHERE name = ? OR address = ?", (person.lower(), address))
            if cursor.fetchone():
                return f"Person '{person}' or address '{address}' already exists."
            cursor.execute("INSERT INTO persons (name, address) VALUES (?, ?)", (person.lower(), address))
            conn.commit()
            return f"Action successful: Added '{person}' with address {address}."
    except sqlite3.Error as e:
        return f"Database error: {e}"

@novel_salary_agent.tool_plain
async def transfer_usdt(from_person: str, to_person: str, amount: float) -> str:
    """
    Transfers only usdt by recording the transaction and returns a JSON object confirming the details.
    """
    # Insert the transfer into the database
    insert_result = await execute_sql_query(
        f"INSERT INTO transfers (from_person, to_person, amount, token) VALUES ('{from_person.lower()}', '{to_person.lower()}', {amount}, '{USDT_TOKEN_ADDRESS}');"
    )
    # Prepare the response JSON
    response = TransferUSDCResponse(
        sender=from_person,
        receiver=to_person,
        amount=amount,
        token=USDT_TOKEN_ADDRESS
    )
    return response.model_dump_json(indent=2)

@novel_salary_agent.tool_plain
async def format_json_response(data: dict) -> str:
    """Formats a dictionary as a JSON string with syntax highlighting."""
    try:
        json_str = json.dumps(data, indent=2)
        return Syntax(json_str, "json", theme="solarized-dark", line_numbers=True).render()
    except Exception as e:
        return f"Error formatting JSON: {e}"
# --- Main Application Logic ---

def parse_and_display_response(raw_output: str):
    """Parses agent output to separate thinking from the final response."""
    think_pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    think_match = think_pattern.search(raw_output)

    if think_match:
        thinking_text = think_match.group(1).strip()
        console.print(Panel(
            f"[yellow]{thinking_text}[/yellow]",
            title="🤔 Agent Thinking",
            border_style="yellow",
            expand=False
        ))
        final_output = think_pattern.sub("", raw_output).strip()
    else:
        final_output = raw_output

    if not final_output:
        console.print("[dim]Agent provided thoughts but no final answer.[/dim]")
        return
        
    console.print(f"[bold green]Agent:[/bold green]")
    try:
        if final_output.strip().startswith('{') and final_output.strip().endswith('}'):
             console.print(Syntax(final_output, "json", theme="solarized-dark", line_numbers=True))
        else:
            console.print(f" {final_output}")
    except Exception:
         console.print(f" {final_output}")


async def main():
    """Main function to run the interactive terminal agent."""
    init_db()
    person_address = {
        'guru': '3N2k1z5Z7g8d9f4e2b6c3a1b2d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2',
        'madhur': '1A2b3C4d5E6f7G8h9I0j1K2l3M4n5O6p7Q8r9S0t1U2v3W4x5Y6z7A8b9C0d1E2',
        'shivam': '9Z8Y7X6W5V4U3T2S1R0Q9P8O7N6M5L4K3J2I1H0G9F8E7D6C5B4A3Z2Y1X0W9V8',
        'gaurav': '2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5Y6Z7A8B9C0D1E2F3G4',
        }
    for person, address in person_address.items():
        try:
            await add_person(person, address)
        except Exception as e:
            print("DB init failed. Error:", e)
    console.print("[bold blue]Welcome to the Novel Salary Agent![/bold blue]")
    console.print(Text(ASCII_ART, style="bold blue"))
    console.print(Panel.fit(
        "[bold cyan]Novel Salary Agent[/bold cyan] | [dim]Ask about persons, transfers, or query the database directly.[/dim]",
        style="blue"
    ))
    console.print("[bold green] Powered by IO Intelligence API and Pydantic AI[/bold green]")
    console.print("Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to end the session.")
    
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            if user_input.lower() in ["exit", "quit"]:
                console.print("[bold blue]Exiting Novel Salary Agent. Goodbye![/bold blue]")
                break

            if not user_input.strip():
                continue

            with console.status("[bold green]Agent is processing...[/bold green]", spinner="dots"):
                agent_response = await novel_salary_agent.run(user_input)

            console.rule(style="dim white")
            parse_and_display_response(agent_response.output)
            console.rule(style="dim white")

        except Exception as e:
            console.print(f"[bold red]An error occurred: {e}[/bold red]")
            console.rule(style="dim white")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold blue]Exiting Novel Salary Agent. Goodbye![/bold blue]")
    except Exception as e:
        console.print(f"[bold red]A critical error occurred: {e}[/bold red]")