import os
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from parser import extract_function
from rate_limiter import groq_rate_limiter

class AgentState(TypedDict):
    """The graph state schema"""
    error_log: str
    file_path: str
    function_name: str
    extracted_code: str
    patch: str
    test_result: str
    iterations: int

class TriageOutput(BaseModel):
    file_path: str = Field(description="The path to the file where the error occurred")
    function_name: str = Field(description="The name of the failing function within that file")

class EngineerOutput(BaseModel):
    patch: str = Field(description="The fully corrected source code for the failing function")

async def triage_node(state: AgentState) -> AgentState:
    print("--- \033[94mTRIAGE AGENT (8B)\033[0m ---")
    await groq_rate_limiter.acquire()
    
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
    structured_llm = llm.with_structured_output(TriageOutput)
    
    prompt = PromptTemplate.from_template(
        "You are an expert triage agent. Analyze the following CI/CD error log.\n"
        "Identify the file path and the exact function name that caused the failure.\n\n"
        "Error Log:\n{error_log}"
    )
    chain = prompt | structured_llm
    
    result = await chain.ainvoke({"error_log": state["error_log"]})
    print(f"-> Identified Error in {result.file_path} at function {result.function_name}")
    return {"file_path": result.file_path, "function_name": result.function_name}

async def extraction_node(state: AgentState) -> AgentState:
    print("--- \033[96mEXTRACTION NODE (AST)\033[0m ---")
    extracted_code = extract_function(state["file_path"], state["function_name"])
    print(f"-> Extracted {len(extracted_code)} characters of context from function '{state['function_name']}'")
    return {"extracted_code": extracted_code}

async def engineer_node(state: AgentState) -> AgentState:
    print("--- \033[93mENGINEER AGENT (70B)\033[0m ---")
    await groq_rate_limiter.acquire()
    
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)
    structured_llm = llm.with_structured_output(EngineerOutput)
    
    prompt = PromptTemplate.from_template(
        "You are an expert engineer. Fix the following Python function based on the error log.\n\n"
        "Error Log:\n{error_log}\n\n"
        "Failing Function Code:\n{extracted_code}\n\n"
        "Return ONLY the fully corrected function source code. It should be a drop-in replacement."
    )
    chain = prompt | structured_llm
    
    result = await chain.ainvoke({"error_log": state["error_log"], "extracted_code": state["extracted_code"]})
    print("-> Successfully generated source code patch.")
    return {"patch": result.patch}

async def test_node(state: AgentState) -> AgentState:
    print("--- \033[92mTEST NODE (SANDBOX STUB)\033[0m ---")
    iterations = state.get("iterations", 0) + 1
    
    # In Phase 3, this function will create an Alpine/Ubuntu Docker container, 
    # mount the patch, run pytest, and collect standard output natively.
    # For now, we simulate a mock output based on iteration count.
    
    if iterations < 3:
        test_result = "fail"
        new_error_log = f"Simulated Docker sandbox test error: Assertion failed at iteration {iterations}."
        print(f"-> Test failed (Simulated). Iteration {iterations}")
        return {"test_result": test_result, "iterations": iterations, "error_log": new_error_log}
    else:
        test_result = "pass"
        print(f"-> Test passed (Simulated). Iteration {iterations}")
        return {"test_result": test_result, "iterations": iterations}

def route_after_test(state: AgentState):
    if state["test_result"] == "pass":
        print("--- \033[95mPR SUBMISSION ROUTED\033[0m ---")
        return END
    elif state["iterations"] >= 3:
        print("--- \033[91mMAX RETRIES REACHED. TERMINATING.\033[0m ---")
        return END
    else:
        print("--- \033[91mTEST FAILED. ROUTING TO TRIAGE FOR REPAIR\033[0m ---")
        return "triage_node"

builder = StateGraph(AgentState)
builder.add_node("triage_node", triage_node)
builder.add_node("extraction_node", extraction_node)
builder.add_node("engineer_node", engineer_node)
builder.add_node("test_node", test_node)

builder.set_entry_point("triage_node")
builder.add_edge("triage_node", "extraction_node")
builder.add_edge("extraction_node", "engineer_node")
builder.add_edge("engineer_node", "test_node")
builder.add_conditional_edges("test_node", route_after_test)

graph = builder.compile()
