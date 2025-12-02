# Human-in-the-Loop Clarification System

## Overview
The chat system now includes intelligent confidence-based routing with human-in-the-loop clarification for ambiguous queries.

## How It Works

### 1. Intent Scoring
Every user message is analyzed and scored across 6 intent categories:
- **Transcribe** (audio transcription)
- **Objects** (object detection in video)
- **Graphs** (chart/graph identification)
- **PowerPoint** (presentation generation)
- **PDF** (document generation)
- **Summary** (conversation summarization)

Each intent receives a confidence score from 0-10:
- **10**: Very strong signal (e.g., "transcribe the video")
- **7-9**: Clear intent (e.g., "transcribe")
- **5-6**: Weak signal (e.g., "object" without context)
- **0-4**: Very weak or no signal

### 2. Clarification Triggers

The system asks for clarification when:
- **Ambiguous Query**: Multiple weak signals (score < 6) detected
- **Low Confidence**: Single intent with score < 6
- **No Intent**: No recognizable intent in the message

### 3. Clarification Messages

#### Example 1: No Clear Intent
**User:** "Can you help me with this?"

**System:**
```
I'm not sure what you'd like me to do with this video. Could you provide more details? For example:
- "Transcribe the video"
- "What objects are shown in the video?"
- "Are there any graphs?"
- "Create a PowerPoint with key points"
- "Summarize our discussion and generate a PDF"
```

#### Example 2: Multiple Weak Signals
**User:** "Tell me about the presentation"

**System:**
```
I detected multiple possible actions. Which would you like me to do?
1. detect objects in the video
2. create a PowerPoint presentation
3. generate a PDF document

Please specify by number or rephrase your request.
```

#### Example 3: Single Weak Signal
**User:** "objects"

**System:**
```
Did you mean: detect objects in the video? If so, please confirm or provide more details.
```

### 4. Numeric Responses

Users can respond to clarification with a number:
- `1` → "transcribe the video"
- `2` → "what objects are shown in the video"
- `3` → "are there any graphs or charts"
- `4` → "create a powerpoint presentation"
- `5` → "generate a pdf document"
- `6` → "summarize our conversation"

### 5. High-Confidence Auto-Execution

Queries with confidence score ≥ 7 are executed immediately without clarification:
- "Transcribe the video" (score: 10)
- "What objects are shown?" (score: 10)
- "Create a PowerPoint with key points" (score: 10)

## Benefits

1. **Prevents Errors**: Avoids executing wrong actions on ambiguous queries
2. **User-Friendly**: Provides clear options and examples
3. **Efficient**: High-confidence queries execute immediately
4. **Flexible**: Accepts both natural language and numeric responses
5. **Conversational**: Maintains natural dialogue flow

## Technical Details

### Confidence Threshold
- **Auto-execution threshold**: 7
- **Clarification threshold**: < 6
- **Ambiguity detection**: Multiple intents with score < 6

### Keyword Patterns
Strong signals (score 10):
- "transcribe the video", "transcript of"
- "what objects", "detect objects"
- "are there...graphs/charts"
- "create a powerpoint", "generate powerpoint"
- "summarize...pdf"

Moderate signals (score 6-8):
- "transcribe", "what is said"
- "object", "what is shown"
- "graph", "chart", "diagram"
- "powerpoint", "ppt", "presentation"
- "summarize", "summary", "recap"

### State Persistence
- User messages are always saved to chat history
- Clarification messages are also saved as assistant responses
- Numeric responses are resolved and the original user input is preserved

## Examples in Practice

### Clear Single Intent
```
User: "Transcribe the video"
→ Executes immediately (confidence: 10)
```

### Ambiguous Multi-Intent
```
User: "Analyze this presentation"
→ Asks for clarification between object detection, PowerPoint, and PDF
```

### Low Confidence Correction
```
User: "charts"
System: "Did you mean: identify charts or graphs? If so, please confirm or provide more details."
User: "yes"
→ Executes graph identification
```

### Numeric Response Flow
```
User: "Help me with this video"
System: [Lists 6 options]
User: "1"
→ Executes transcription
```

## Future Enhancements

Potential improvements:
- Context-aware scoring (learn from user's previous queries)
- Multi-language support for intent detection
- Custom user preferences for clarification verbosity
- Integration with speech recognition for voice queries








