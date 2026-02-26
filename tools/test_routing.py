from ALICE_v2 import split_commands
import context_manager

samples = [
    "open calculator",
    "please open calculator",
    "what's the weather today",
    "run: dir C:\\",
    "open calculator and then close chrome",
]

cm = context_manager.ContextManager()
for s in samples:
    intent = cm.analyze_intent(s)
    entities = cm.extract_entities(s)
    routed = cm.route_command(s, intent, entities)
    print('INPUT:', s)
    print('  intent:', intent)
    print('  entities:', entities)
    print('  routed:', routed)
    print('-'*40)
