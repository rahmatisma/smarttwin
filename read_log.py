import pathlib, sys
p = pathlib.Path(r'C:\Users\santi\.gemini\antigravity-ide\brain\d426c9a5-e5e0-4d62-9fb6-4786e795ba03\.system_generated\tasks\task-283.log')
if p.exists():
    print(p.read_text('utf-8'))
else:
    print('Not found')
