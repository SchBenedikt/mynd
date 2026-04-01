# Autonomous AI Agent & Enhanced Search Integration

## Overview

The MYND AI assistant now features a fully autonomous agent system that proactively researches, gathers information, and synthesizes comprehensive answers from multiple data sources without requiring explicit instructions for each step.

## Key Features

### 1. Autonomous Agent Framework

The autonomous agent (`backend/core/autonomous/agent.py`) enables the AI to:

- **Plan Multi-Step Actions**: Analyzes user queries and automatically plans relevant research actions
- **Execute Research Tasks**: Performs searches across multiple sources independently
- **Synthesize Results**: Combines information from all sources into coherent context
- **Self-Directed Learning**: Adapts search strategies based on query intent

### 2. Comprehensive Search Integration

#### Nextcloud Unified Search API
- Searches across **all** Nextcloud providers simultaneously:
  - 📁 Files
  - 👤 Contacts
  - 📅 Calendar Events
  - ✅ Tasks
  - 💬 Talk
  - 📋 Deck
- Automatically extracts relevant search terms from user queries
- Groups and formats results for AI consumption

#### Knowledge Base (Indexed Documents)
- Full-text search through all indexed documents
- Returns document chunks with relevance scores
- Enhanced with training manager metadata

#### Immich Photo Search
- Intelligent photo search with metadata
- Object, person, and location recognition
- Direct image embedding in responses

### 3. Autonomous Action Types

The agent can execute the following actions autonomously:

| Action Type | Description | Priority |
|-------------|-------------|----------|
| `SEARCH_KNOWLEDGE_BASE` | Search indexed documents | High (9) |
| `SEARCH_FILES` | Search Nextcloud files | High (8) |
| `SEARCH_PHOTOS` | Search Immich photos | High (8) |
| `SEARCH_CONTACTS` | Search contacts | Medium (7) |
| `SEARCH_CALENDAR` | Search calendar events | Medium (7) |
| `SEARCH_TASKS` | Search tasks/todos | Medium (7) |
| `READ_FILE` | Read specific file content | Medium |
| `LIST_DIRECTORY` | List directory contents | Low |
| `ANALYZE_DOCUMENT` | Parse and analyze documents | Medium |
| `SYNTHESIZE_INFORMATION` | Combine multiple sources | Low |

### 4. Intelligent Query Analysis

The agent automatically:

1. **Extracts Keywords**: Removes stop words and identifies meaningful search terms
2. **Detects Intent**: Identifies if query relates to:
   - People/contacts (searches contacts)
   - Time/events (searches calendar)
   - Tasks (searches todos)
   - Visual content (searches photos)
   - Documents (searches knowledge base)
3. **Plans Actions**: Creates prioritized action list based on query analysis
4. **Executes Parallel Searches**: Runs multiple searches simultaneously for speed

## How It Works

### Query Flow with Autonomous Agent

```
User Query: "Zeig mir alle Infos zum Meum Diarium"
    ↓
┌─────────────────────────────────────────────────┐
│  1. Extract Keywords: ["meum", "diarium"]       │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  2. Plan Autonomous Actions (Parallel):         │
│     - Search Knowledge Base (indexed docs)      │
│     - Search Nextcloud Files                    │
│     - Search Nextcloud Unified Search           │
│     - Search Photos if relevant                 │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  3. Execute All Searches Simultaneously         │
│     ✓ Knowledge Base: 12 chunks found          │
│     ✓ Nextcloud Files: 5 files found           │
│     ✓ Unified Search: 8 results (files,tasks)  │
│     ✓ Photos: 3 photos found                   │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  4. Format & Combine All Results                │
│     - Group by source type                      │
│     - Add metadata and relevance scores         │
│     - Create comprehensive context              │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│  5. AI Generates Comprehensive Response         │
│     Using all gathered information:             │
│     - Document content from knowledge base      │
│     - File references from Nextcloud            │
│     - Related calendar events                   │
│     - Photos with embedded links                │
│     - Related contacts                          │
└─────────────────────────────────────────────────┘
```

### Integration Points

#### In `app.py` (`agent_query` endpoint):

```python
# 1. Nextcloud Unified Search (Proactive)
nextcloud_search_context = gather_nextcloud_search_context(
    search_client, prompt, extract_search_terms
)

# 2. Autonomous Agent (Multi-Source Research)
agent = AutonomousAgent(
    nextcloud_client=nextcloud_client,
    search_client=search_client,
    knowledge_base=knowledge_base,
    immich_client=immich_client,
    training_manager=training_manager
)

planned_actions = agent.analyze_query_and_plan_actions(prompt, context)
results = agent.execute_actions(planned_actions, username)
autonomous_context = agent.format_autonomous_results_for_context(results)

# 3. Combine with traditional contexts
combined_context = combine_contexts(
    weather_context,
    security_context,
    activity_context,
    photo_context,
    file_context,
    calendar_context,
    todo_context,
    nextcloud_search_context  # NEW
)

# 4. Add autonomous research
if autonomous_context:
    combined_context.append(autonomous_context)
```

## Configuration

### Enable/Disable Autonomous Mode

In `app.py` line 5463:

```python
autonomous_enabled = True  # Set to False to disable autonomous research
```

### Customize Action Planning

Edit `backend/core/autonomous/agent.py`, method `analyze_query_and_plan_actions()`:

- Adjust keyword indicators for each action type
- Modify priority levels (1-10, higher = more important)
- Add new action types
- Change result limits

### Search Term Extraction

Edit `extract_search_terms()` in `app.py`:

- Customize stop words list
- Adjust number of keywords extracted (currently 3-5)
- Add domain-specific filtering

## API Response Format

The agent now returns additional fields:

```json
{
  "success": true,
  "response": "AI generated response using all sources...",
  "context_used": true,
  "context_count": 8,
  "intent": "files",
  "sources_used": {
    "photos": true,
    "files": true,
    "calendar": false,
    "todos": false,
    "nextcloud_search": true,
    "autonomous_research": true
  }
}
```

## Examples

### Example 1: Comprehensive Topic Research

**Query:** "Was weißt du über mein Diarium Projekt?"

**Autonomous Actions Executed:**
1. ✓ Search Knowledge Base → Found 15 document chunks
2. ✓ Search Nextcloud Files → Found 8 related files
3. ✓ Nextcloud Unified Search → Found 12 results across providers
4. ✓ Search Tasks → Found 3 related tasks

**Result:** Comprehensive answer combining all information sources

### Example 2: Person Search

**Query:** "Wer ist Max Mustermann und welche Kontakte habe ich?"

**Autonomous Actions Executed:**
1. ✓ Search Contacts → Found contact details
2. ✓ Search Knowledge Base → Found mentions in documents
3. ✓ Nextcloud Unified Search → Found related files and calendar events

**Result:** Complete profile with contact info, related documents, and events

### Example 3: Visual Content

**Query:** "Zeig mir Fotos vom letzten Urlaub in Italien"

**Autonomous Actions Executed:**
1. ✓ Search Photos → Found 25 photos with location "Italy"
2. ✓ Search Knowledge Base → Found travel documents
3. ✓ Search Files → Found itinerary and booking confirmations

**Result:** Photos with embedded thumbnails + travel documents

## Performance Considerations

### Parallel Execution
All autonomous actions execute in parallel using Python's built-in capabilities, significantly reducing total research time.

### Caching
- Knowledge base results are cached
- Nextcloud credentials are reused across actions
- Training manager maintains session state

### Timeouts
- Each action has individual timeout protection
- Failed actions don't block others
- Graceful degradation if some sources fail

## Security

### Safe by Design
- No file write operations without explicit user action
- Read-only access to all data sources
- Authentication required for all API calls
- User-specific credential isolation

### Action Logging
All autonomous actions are logged:
```
[INFO] Starting autonomous research...
[INFO] Autonomous agent planned 5 actions
[INFO] Executing action: Search indexed documents for: diarium, projekt
[INFO] Found 15 relevant document chunks
[INFO] Autonomous research completed successfully
```

## Future Enhancements

Potential additions to the autonomous agent:

1. **File Content Analysis**: Automatically read and summarize related files
2. **Cross-Reference Detection**: Find connections between different sources
3. **Temporal Analysis**: Track changes in documents over time
4. **Recommendation Engine**: Suggest related content proactively
5. **Learning from Feedback**: Improve action planning based on user responses
6. **Custom Action Scripts**: Allow users to define custom research workflows
7. **Collaborative Filtering**: Learn from patterns across multiple queries

## Troubleshooting

### Agent Not Executing Actions

Check logs for:
```
[WARNING] Autonomous agent error: ...
```

Common causes:
- Nextcloud not configured (`NEXTCLOUD_URL`, credentials missing)
- Knowledge base not indexed
- Search client initialization failed

### No Results from Autonomous Research

Verify:
1. Knowledge base has been indexed: `/api/indexing/status`
2. Nextcloud search is accessible
3. Keywords are being extracted correctly (check logs)

### Performance Issues

If searches are slow:
1. Reduce action limits in `agent.py`
2. Disable autonomous mode for simple queries
3. Check Nextcloud server response times
4. Review indexing database size

## Related Files

- `backend/core/autonomous/agent.py` - Main autonomous agent implementation
- `backend/core/context/gatherers.py` - Context gathering functions including Nextcloud search
- `backend/core/app.py` - Integration point in `agent_query()` endpoint
- `backend/features/integration/search_client.py` - Nextcloud Unified Search API client
- `backend/features/knowledge/indexing.py` - Document indexing system
- `backend/features/training/manager.py` - Training and context enhancement

## Testing

### Manual Testing

1. **Test Nextcloud Search:**
```bash
curl -X POST http://localhost:5000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "prompt": "Finde Dateien über Projekt", "language": "de"}'
```

2. **Test Autonomous Research:**
```bash
curl -X POST http://localhost:5000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "prompt": "Was weißt du über mein Diarium?", "language": "de"}'
```

3. **Check Logs:**
```bash
# Look for autonomous agent activity
grep "autonomous" backend.log
grep "Nextcloud search" backend.log
```

### Verification Checklist

- [ ] Autonomous agent initializes without errors
- [ ] Nextcloud search client connects successfully
- [ ] Actions are planned based on query keywords
- [ ] Multiple sources are searched in parallel
- [ ] Results are formatted and combined correctly
- [ ] AI uses autonomous research in responses
- [ ] Error handling works gracefully
- [ ] Logging provides sufficient debug information

## Summary

The autonomous agent transforms MYND from a reactive assistant into a proactive research system that:

✅ **Understands** user intent from natural language
✅ **Plans** multi-step research strategies
✅ **Executes** searches across all available data sources
✅ **Synthesizes** comprehensive answers from diverse information
✅ **Operates** independently without step-by-step instructions

This implementation fulfills the requirement: *"Das System sollte meine Dateien kennen, alles über mich wissen. Die KI darf gerne in kleinere Schritte selbsständig agieren, Recherche betreiben, Aktionen durchführen."*
