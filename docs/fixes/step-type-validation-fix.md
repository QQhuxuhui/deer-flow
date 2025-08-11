# DeerFlow Issue Fix: Missing step_type Field

## Problem
The DeerFlow planner node was failing with a Pydantic validation error because the LLM-generated plan JSON was missing the required `step_type` field for each step.

## Error Details
```
pydantic_core._pydantic_core.ValidationError: 3 validation errors for Plan
steps.0.step_type
  Field required [type=missing, input_value={'need_search': True, 'ti...的完整数据链。'}, input_type=dict]
```

## Root Cause Analysis
1. The LLM was generating step objects without the required `step_type` field
2. The prompt template mentioned `step_type` but didn't emphasize it strongly enough
3. No fallback logic existed to handle missing fields during parsing

## Solution Implementation

### 1. Enhanced Prompt Template
**File**: `src/prompts/planner.md`
- Added **CRITICAL** section emphasizing the requirement for `step_type` field
- Provided clear mapping: `need_search: true` → `step_type: "research"`
- Added concrete JSON example showing proper format

### 2. Fallback Logic in Node Processing
**File**: `src/graph/nodes.py`
- Added validation logic in `planner_node()` (lines 138-147)
- Added validation logic in `human_feedback_node()` (lines 208-217)
- Automatically infers `step_type` based on `need_search` value if missing
- Logs when step_type is auto-added for debugging

### 3. Inference Rules
```python
if step.get("need_search", True):
    step["step_type"] = "research"    # Information gathering
else:
    step["step_type"] = "processing"  # Data analysis/computation
```

## Fix Verification

### Test Case
The error occurred with this LLM-generated JSON:
```json
{
  "steps": [{
    "need_search": true,
    "title": "获取徐州实时天气详情",
    "description": "收集徐州当前实时天气数据..."
    // Missing: "step_type" field
  }]
}
```

### Expected Result After Fix
```json
{
  "steps": [{
    "need_search": true,
    "title": "获取徐州实时天气详情", 
    "description": "收集徐州当前实时天气数据...",
    "step_type": "research"  // Auto-added by fallback logic
  }]
}
```

## Benefits
1. **Backward Compatibility**: Handles both new LLM responses and legacy formats
2. **Robust Error Handling**: Graceful degradation when fields are missing
3. **Debugging Support**: Logs when auto-correction occurs
4. **Future-Proof**: Enhanced prompt should reduce missing fields going forward

## Testing Recommendations
1. Test with various LLM providers to ensure consistent `step_type` generation
2. Verify fallback logic works for both research and processing steps
3. Monitor logs for auto-correction frequency to assess prompt effectiveness

This fix ensures the DeerFlow planner remains robust while improving LLM output compliance.