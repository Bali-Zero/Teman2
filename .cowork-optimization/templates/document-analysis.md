# Document Analysis Template

## Task Description
Analyze documents in [FOLDER_PATH] and extract:
- Key topics and themes
- Important dates and deadlines
- Action items and TODOs
- People and organizations mentioned
- Summary of each document

## Instructions
1. Read all documents in [FOLDER_PATH]
2. For each document, extract:
   - Title/filename
   - Date created/modified
   - Main topics (3-5 keywords)
   - Key insights (2-3 sentences)
   - Action items (if any)
   - Related documents

3. Create master summary document with:
   - Index of all documents
   - Topic clustering
   - Timeline of important dates
   - Cross-references between docs

## Output Format
```markdown
# Document Analysis Report
Generated: [DATE]

## Summary
- Total documents: [N]
- Date range: [START] - [END]
- Main topics: [LIST]

## Documents by Topic

### [TOPIC 1]
- Document 1: [SUMMARY]
- Document 2: [SUMMARY]

### [TOPIC 2]
...

## Action Items
- [ ] Item 1 (from doc X)
- [ ] Item 2 (from doc Y)

## Timeline
- [DATE]: Event/Deadline from doc Z
```
