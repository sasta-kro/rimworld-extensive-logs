import json

with open("your_output.json", "r") as f:
    logs = json.load(f)

for log in logs:
    date = log["human_date"]

    if log["type"] == "tale" and log["pawn"]:
        print(f"[{date}] EVENT: {log['pawn']} triggered {log['def']}.")

    elif log["type"] == "playlog_interaction":
        print(f"[{date}] SOCIAL: {log['initiator']} did {log['interactionDef']} with {log['recipient']}.")