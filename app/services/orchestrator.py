import asyncio
import json

from app.services.agents import get_attacker_response, get_target_response, run_security_audit


async def run_redteam_simulation(turns: int = 4):
    print("🚀 Starting AI Red Teaming Simulation...")
    print("=" * 60)
    
    # 1. Initialize conversation state
    chat_history = [
        {"role": "assistant", "content": "Hello! Welcome to TechMart. How can I help you today?"}
    ]
    print(f"🛡️ [Target Initial]: {chat_history[0]['content']}\n")

    # 2. Execute the Bot-vs-Bot Chat Loop
    for turn in range(1, turns + 1):
        print(f"⏱️ --- TURN {turn} ---")
        
        # Attacker Bot generates an exploit attempt
        attacker_text = await get_attacker_response(chat_history)
        print(f"💀 [Attacker / Hacker]:\n{attacker_text}\n")
        
        # Save attack to history (seen as 'user' by the Target)
        chat_history.append({"role": "user", "content": attacker_text})
        
        # Target Bot defends itself
        target_text = await get_target_response(chat_history)
        print(f"🛡️ [Target Bot Response]:\n{target_text}\n")
        
        # Save response to history
        chat_history.append({"role": "assistant", "content": target_text})
        print("-" * 40)
        
    print("\n🏁 Chat simulation complete. Initializing Security Audit...")
    print("=" * 60)
    
    # 3. Run the Security Evaluation (Judge Bot)
    # The judge evaluates the transcript and returns a native Pydantic object
    audit_report = await run_security_audit(chat_history)
    
    print("🔍 [JUDGE VERDICT RECEIVED]:\n")
    # Convert Pydantic object to a beautifully formatted JSON string
    report_json = json.dumps(audit_report.model_dump(), indent=4, ensure_ascii=False)
    print(report_json)
    
    return audit_report

if __name__ == "__main__":
    # Ensure local path resolving works smoothly when running directly
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    asyncio.run(run_redteam_simulation(turns=4))
