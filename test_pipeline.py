import asyncio
import subprocess
import os
from dotenv import load_dotenv

# Load API key before importing the graph (which initializes Langchain-Groq calls)
load_dotenv()

from state_machine import graph

async def main():
    print("====================================")
    print("1. RUNNING PYTEST LOCALLY TO GENERATE ERROR LOG")
    print("====================================")
    
    # Run pytest on our dummy file
    result = subprocess.run(["pytest", "test_math.py"], capture_output=True, text=True)
    error_log = result.stdout + result.stderr
    
    print("\n[Tests Failed] Generating swarm context...\n")
    
    initial_state = {
        "error_log": error_log,
        "file_path": "",
        "function_name": "",
        "extracted_code": "",
        "patch": "",
        "test_result": "",
        "iterations": 0
    }

    print("====================================")
    print("2. INITIATING SELF-HEALING SWARM")
    print("====================================")
    
    # Stream the langgraph execution
    async for chunk in graph.astream(initial_state):
        for node_name, node_state in chunk.items():
            print(f"\n✅ Finished processing node: {node_name}")
            if node_name == "engineer_node":
                print(f"-> Generated Patch:\n{node_state.get('patch', '')}")
            elif node_name == "test_node":
                print(f"-> Verification Result: {node_state.get('test_result', '')}")

    print("\n====================================")
    print("SWARM EXECUTION COMPLETE")
    print("====================================")

if __name__ == "__main__":
    asyncio.run(main())
