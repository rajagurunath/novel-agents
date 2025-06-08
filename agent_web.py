#!/usr/bin/env python3

import asyncio
import sqlite3
import json
import re
from typing import List

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic import BaseModel
import streamlit as st
st.set_page_config(page_title="Novel Salary Agent Chat", page_icon="💸", layout="wide")

# --- Configuration & Setup ---
# Ensures both CLI and Streamlit app use the same database file
DB_FILE = "salary_agent.db"
USDT_TOKEN_ADDRESS = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

# IO Intelligence API configuration
IO_API_KEY = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjJlNWNiNzA0LTdiNWEtNDFjOS04NjQ5LTA4ZWFhNzZiYmJhNSIsImV4cCI6NDkwMjk3NDkxNn0.pa3cp35NXcgaJZCWJ7Y0ozWh7Jv1omodrBcTkbz96RQxTr7KdEB4gxidydpSUfCM3_jPNqZVYjaCDZ423g58Jw"
IO_BASE_URL = "https://api.intelligence.io.solutions/api/v1"

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

# --- Agent Definition (Identical to CLI) ---
# @st.cache_resource
def get_agent():
    """Caches the agent for performance across reruns."""
    model = OpenAIModel(
        model_name='Qwen/Qwen3-235B-A22B-FP8',
        provider=OpenAIProvider(base_url=IO_BASE_URL, api_key=IO_API_KEY),
    )
    return Agent(
        model=model,
        deps_type=str,
        auto_execute_tools=True,
        system_prompt=(
            '''
            YOU are a world-class Novel Salary Agent, an expert in managing Solana wallets and executing SQL queries.

            **Your Response Structure:**
            1.  **Think Step-by-Step:** First, analyze the user's request. Enclose your reasoning in <think> and </think> tags. Inside, explain which tool you will use. If using the SQL tool, write the exact SQL query you will execute.
            2.  **Provide a Final, Clean Answer:** After the </think> tag, give the user the final answer.

            **Database Schema for SQL Queries:**
            You have access to the following two tables. Use this schema to construct your queries for the `execute_sql_query` tool.

            ```sql
            CREATE TABLE persons (name TEXT PRIMARY KEY, address TEXT NOT NULL UNIQUE);
            CREATE TABLE transfers (id INTEGER PRIMARY KEY, from_person TEXT, to_person TEXT, amount REAL, token TEXT, timestamp DATETIME);
            ```
            Important : for transfer_usdt tool which returns json, make sure to show the json response in a formatted way in output along with your response.
            '''
        ),
    )

novel_salary_agent = get_agent()

# --- All Tools (Identical to CLI, but adapted for Streamlit's async context) ---
@novel_salary_agent.tool_plain
async def execute_sql_query(query: str) -> str:
    """Executes a SQL query. For SELECT, returns a JSON string with columns and data. For others, a status message."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                conn.commit()
                if not rows: return "Query executed, but returned no results."
                # Return a JSON string for the agent and for the UI to parse
                return json.dumps({"type": "dataframe", "columns": columns, "data": rows})
            else:
                rc = cursor.rowcount
                conn.commit()
                return f"Query executed successfully. {rc} rows affected."
    except sqlite3.Error as e: return f"Database Error: {e}"

# (Other tools remain the same, as they ultimately call execute_sql_query or return specific formats)
@novel_salary_agent.tool_plain
def list_persons_with_addresses() -> str:
    return asyncio.run(execute_sql_query("SELECT name, address FROM persons ORDER BY name"))

@novel_salary_agent.tool_plain
async def add_person(person: str, address: str) -> str:
    return await execute_sql_query(f"INSERT OR IGNORE INTO persons (name, address) VALUES ('{person.lower()}', '{address}')")

@novel_salary_agent.tool_plain
async def transfer_usdt(from_person: str, to_person: str, amount: float) -> str:
    await execute_sql_query(
        f"INSERT INTO transfers (from_person, to_person, amount, token) VALUES ('{from_person.lower()}', '{to_person.lower()}', {amount}, '{USDT_TOKEN_ADDRESS}');"
    )
    response = TransferUSDCResponse(sender=from_person, receiver=to_person, amount=amount)
    return response.model_dump_json(indent=2)


# --- Streamlit Application UI ---


# Run DB initialization and seeding once
init_db()
if 'db_seeded' not in st.session_state:
    with st.spinner("Seeding initial database..."):
        initial_persons = {
            'guru': '3N2k1z5Z7g8d9f4e2b6c3a1b2d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2',
            'madhur': '1A2b3C4d5E6f7G8h9I0j1K2l3M4n5O6p7Q8R9S0t1U2v3W4x5Y6z7A8b9C0d1E2',
            'shivam': '9Z8Y7X6W5V4U3T2S1R0Q9P8O7N6M5L4K3J2I1H0G9F8E7D6C5B4A3Z2Y1X0W9V8',
            'gaurav': '2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5Y6Z7A8B9C0D1E2F3G4',
        }
        for person, address in initial_persons.items():
            try:
                # Use a synchronous connection for setup
                with sqlite3.connect(DB_FILE) as conn:
                    conn.execute("INSERT OR IGNORE INTO persons (name, address) VALUES (?, ?)", (person, address))
            except Exception:
                pass # Ignore if already exists
    st.session_state.db_seeded = True


st.title("💸 Novel Salary Agent")
st.code(ASCII_ART, language=None)
st.caption("I can manage Solana wallets, transfer USDT, and answer complex questions about the data via SQL.")
st.caption("Powered by IO Intelligence API and Pydantic AI.")
# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

def display_agent_response(raw_output: str):
    """Parses raw agent output and displays it in the Streamlit UI."""
    think_pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    think_match = think_pattern.search(raw_output)

    if think_match:
        thinking_text = think_match.group(1).strip()
        with st.expander("🤔 Agent's Thoughts"):
            st.info(thinking_text)
        final_output = think_pattern.sub("", raw_output).strip()
    else:
        final_output = raw_output.strip()

    if final_output:
        try:
            # Check if the output is JSON and display it nicely
            json_data = json.loads(final_output)
            st.json(json_data)
        except (json.JSONDecodeError, TypeError):
            # Otherwise, display as code/markdown for tables and text
            st.code(final_output, language=None)

# Display past messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            # Re-render the complex agent response
            display_agent_response(message["content"])

# Main chat input
if prompt := st.chat_input("Ask 'list persons' or 'transfer 100 from guru to shivam'"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Run async agent code within Streamlit's sync flow
                agent_response = asyncio.run(novel_salary_agent.run(prompt))
                response_text = agent_response.output
            except Exception as e:
                response_text = f"An error occurred: {e}"

        display_agent_response(response_text)

    # Add raw agent response to history for consistent re-rendering
    st.session_state.messages.append({"role": "assistant", "content": response_text})