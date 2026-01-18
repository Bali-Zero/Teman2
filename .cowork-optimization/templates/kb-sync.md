# Knowledge Base Sync Template

## Task Description

Sync Knowledge Base files to Qdrant vector database for RAG system

## Instructions

1. Scan KB directories:
   - ~/Desktop/KB/
   - ~/Desktop/kbli/
   - ~/Desktop/nuzantara/apps/kb/

2. Identify new/modified files since last sync
3. Process files:
   - Extract text content
   - Generate embeddings
   - Create metadata
   - Upload to Qdrant

4. Verify sync completion

## File Types to Process

- ✅ Markdown (.md)
- ✅ Text (.txt)
- ✅ JSON (.json)
- ✅ PDF (.pdf)
- ✅ Word (.doc, .docx)
- ❌ Images (skip)
- ❌ Videos (skip)

## Metadata to Extract

- filename
- filepath
- file_size
- created_date
- modified_date
- content_type
- tags (if available)
- source (KB/kbli/other)

## Output

```markdown
# KB Sync Report

Date: [DATE]

## Summary

- Files scanned: [N]
- New files: [N]
- Modified files: [N]
- Total synced: [N]
- Errors: [N]

## Qdrant Status

- Collection: [NAME]
- Total vectors: [N]
- Index updated: Yes/No

## Details

### Successfully Synced

- file1.md (2.3KB)
- file2.json (15KB)

### Errors

- file3.pdf: Error message

## Next Steps

- Review error files
- Verify search functionality
- Update KB documentation
```

## Safety Rules

- Backup Qdrant collection before sync
- Validate embeddings quality
- Log all operations
- Rollback on critical errors
