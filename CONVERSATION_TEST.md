# Testing Conversation CLI

## Manual Testing (Recommended)

### 1. Start Interactive Session
```bash
cd /Users/ntutt/chariot-dev/chariot-development-platform/modules/praetorian-cli
python3 -m praetorian_cli.main chariot agent conversation
```

### 2. Test Commands
Once the CLI starts, try these commands:

**Basic Commands:**
- `help` - Show available commands and examples
- `clear` - Clear the screen
- `new` - Start a new conversation

**Test Queries:**
- `hello` - Simple greeting (should not trigger tools)
- `find all active assets` - Should trigger query tool and show summary + truncated results
- `show me critical risks` - Should execute risk query
- `what assets do we have for example.com?` - Domain-specific query

**Exit:**
- `quit` or `exit` or `q` - Exit the conversation

## Expected Output

### Normal Response (No Tools)
```
┌─ Chariot AI ─────────────────────────────┐
│ Hello! I'm your security assistant...    │
└──────────────────────────────────────────┘
```

### Tool Response (With Summarization)
```
┌─ Chariot AI ─────────────────────────────┐
│ I found 47 active assets across your     │
│ infrastructure. Most are cloud resources │  
│ with some notable security findings...    │
└──────────────────────────────────────────┘

┌─ Tool Output Preview (5/47 lines) ───────┐
│ {                                        │
│   "collection": {                        │
│     "items": {                           │
│       "asset": [                         │
│         {                                │
│ ... [42 more lines truncated]            │
└──────────────────────────────────────────┘
```

## Alternative Testing Methods

### 1. Direct API Testing
```python
# Use the test script we created earlier
python3 test_tool_execution.py
```

### 2. Check CLI Import
```bash
python3 -c "from praetorian_cli.ui.conversation.menu import run_conversation_menu; print('✅ CLI imports successfully')"
```

### 3. Verify Command Registration
```bash
python3 -m praetorian_cli.main chariot agent --help | grep conversation
```

## Troubleshooting

If the CLI doesn't start:
1. Check Python import errors
2. Verify Rich library is installed (`pip install rich`)
3. Check authentication/keychain setup
4. Try running with `--debug` flag

If you see no output:
1. The CLI might be waiting for input
2. Try typing commands and pressing Enter
3. Check terminal/console settings